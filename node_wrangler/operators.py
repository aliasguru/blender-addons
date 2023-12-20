# SPDX-FileCopyrightText: 2013-2023 Blender Foundation
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy

from bpy.types import Operator
from bpy.props import (
    FloatProperty,
    EnumProperty,
    BoolProperty,
    IntProperty,
    StringProperty,
    FloatVectorProperty,
    CollectionProperty,
)
from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy_extras.node_utils import connect_sockets
from mathutils import Vector
from os import path
from glob import glob
from copy import copy
from itertools import chain

from .interface import NWConnectionListInputs, NWConnectionListOutputs

from .utils.constants import blend_types, geo_combine_operations, operations, navs, get_texture_node_types, rl_outputs
from .utils.draw import draw_callback_nodeoutline
from .utils.paths import match_files_to_socket_names, split_into_components
from .utils.nodes import (node_mid_pt, autolink, node_at_pos, get_nodes_links, is_viewer_socket, is_viewer_link,
                          get_group_output_node, get_output_location, force_update, get_internal_socket, nw_check,
                          nw_check_space_type, NWBase, get_first_enabled_output, is_visible_socket, viewer_socket_name)

class NWLazyMix(Operator, NWBase):
    """Add a Mix RGB/Shader node by interactively drawing lines between nodes"""
    bl_idname = "node.nw_lazy_mix"
    bl_label = "Mix Nodes"
    bl_options = {'REGISTER', 'UNDO'}

    def modal(self, context, event):
        context.area.tag_redraw()
        nodes, links = get_nodes_links(context)
        cont = True

        start_pos = [event.mouse_region_x, event.mouse_region_y]

        node1 = None
        if not context.scene.NWBusyDrawing:
            node1 = node_at_pos(nodes, context, event)
            if node1:
                context.scene.NWBusyDrawing = node1.name
        else:
            if context.scene.NWBusyDrawing != 'STOP':
                node1 = nodes[context.scene.NWBusyDrawing]

        context.scene.NWLazySource = node1.name
        context.scene.NWLazyTarget = node_at_pos(nodes, context, event).name

        if event.type == 'MOUSEMOVE':
            self.mouse_path.append((event.mouse_region_x, event.mouse_region_y))

        elif event.type == 'RIGHTMOUSE' and event.value == 'RELEASE':
            end_pos = [event.mouse_region_x, event.mouse_region_y]
            bpy.types.SpaceNodeEditor.draw_handler_remove(self._handle, 'WINDOW')

            node2 = None
            node2 = node_at_pos(nodes, context, event)
            if node2:
                context.scene.NWBusyDrawing = node2.name

            if node1 == node2:
                cont = False

            if cont:
                if node1 and node2:
                    for node in nodes:
                        node.select = False
                    node1.select = True
                    node2.select = True

                    bpy.ops.node.nw_merge_nodes(mode="MIX", merge_type="AUTO")

            context.scene.NWBusyDrawing = ""
            return {'FINISHED'}

        elif event.type == 'ESC':
            print('cancelled')
            bpy.types.SpaceNodeEditor.draw_handler_remove(self._handle, 'WINDOW')
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if context.area.type == 'NODE_EDITOR':
            # the arguments we pass the the callback
            args = (self, context, 'MIX')
            # Add the region OpenGL drawing callback
            # draw in view space with 'POST_VIEW' and 'PRE_VIEW'
            self._handle = bpy.types.SpaceNodeEditor.draw_handler_add(
                draw_callback_nodeoutline, args, 'WINDOW', 'POST_PIXEL')

            self.mouse_path = []

            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "View3D not found, cannot run operator")
            return {'CANCELLED'}


class NWLazyConnect(Operator, NWBase):
    """Connect two nodes without clicking a specific socket (automatically determined"""
    bl_idname = "node.nw_lazy_connect"
    bl_label = "Lazy Connect"
    bl_options = {'REGISTER', 'UNDO'}
    with_menu: BoolProperty()

    def modal(self, context, event):
        context.area.tag_redraw()
        nodes, links = get_nodes_links(context)
        cont = True

        start_pos = [event.mouse_region_x, event.mouse_region_y]

        node1 = None
        if not context.scene.NWBusyDrawing:
            node1 = node_at_pos(nodes, context, event)
            if node1:
                context.scene.NWBusyDrawing = node1.name
        else:
            if context.scene.NWBusyDrawing != 'STOP':
                node1 = nodes[context.scene.NWBusyDrawing]

        context.scene.NWLazySource = node1.name
        context.scene.NWLazyTarget = node_at_pos(nodes, context, event).name

        if event.type == 'MOUSEMOVE':
            self.mouse_path.append((event.mouse_region_x, event.mouse_region_y))

        elif event.type == 'RIGHTMOUSE' and event.value == 'RELEASE':
            end_pos = [event.mouse_region_x, event.mouse_region_y]
            bpy.types.SpaceNodeEditor.draw_handler_remove(self._handle, 'WINDOW')

            node2 = None
            node2 = node_at_pos(nodes, context, event)
            if node2:
                context.scene.NWBusyDrawing = node2.name

            if node1 == node2:
                cont = False

            link_success = False
            if cont:
                if node1 and node2:
                    original_sel = []
                    original_unsel = []
                    for node in nodes:
                        if node.select:
                            node.select = False
                            original_sel.append(node)
                        else:
                            original_unsel.append(node)
                    node1.select = True
                    node2.select = True

                    # link_success = autolink(node1, node2, links)
                    if self.with_menu:
                        if len(node1.outputs) > 1 and node2.inputs:
                            bpy.ops.wm.call_menu("INVOKE_DEFAULT", name=NWConnectionListOutputs.bl_idname)
                        elif len(node1.outputs) == 1:
                            bpy.ops.node.nw_call_inputs_menu(from_socket=0)
                    else:
                        link_success = autolink(node1, node2, links)

                    for node in original_sel:
                        node.select = True
                    for node in original_unsel:
                        node.select = False

            if link_success:
                force_update(context)
            context.scene.NWBusyDrawing = ""
            return {'FINISHED'}

        elif event.type == 'ESC':
            bpy.types.SpaceNodeEditor.draw_handler_remove(self._handle, 'WINDOW')
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if context.area.type == 'NODE_EDITOR':
            nodes, links = get_nodes_links(context)
            node = node_at_pos(nodes, context, event)
            if node:
                context.scene.NWBusyDrawing = node.name

            # the arguments we pass the the callback
            mode = "LINK"
            if self.with_menu:
                mode = "LINKMENU"
            args = (self, context, mode)
            # Add the region OpenGL drawing callback
            # draw in view space with 'POST_VIEW' and 'PRE_VIEW'
            self._handle = bpy.types.SpaceNodeEditor.draw_handler_add(
                draw_callback_nodeoutline, args, 'WINDOW', 'POST_PIXEL')

            self.mouse_path = []

            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "View3D not found, cannot run operator")
            return {'CANCELLED'}


class NWDeleteUnused(Operator, NWBase):
    """Delete all nodes whose output is not used"""
    bl_idname = 'node.nw_del_unused'
    bl_label = 'Delete Unused Nodes'
    bl_options = {'REGISTER', 'UNDO'}

    delete_muted: BoolProperty(
        name="Delete Muted",
        description="Delete (but reconnect, like Ctrl-X) all muted nodes",
        default=True)
    delete_frames: BoolProperty(
        name="Delete Empty Frames",
        description="Delete all frames that have no nodes inside them",
        default=True)

    def is_unused_node(self, node):
        end_types = ['OUTPUT_MATERIAL', 'OUTPUT', 'VIEWER', 'COMPOSITE',
                     'SPLITVIEWER', 'OUTPUT_FILE', 'LEVELS', 'OUTPUT_LIGHT',
                     'OUTPUT_WORLD', 'GROUP_INPUT', 'GROUP_OUTPUT', 'FRAME']
        if node.type in end_types:
            return False

        for output in node.outputs:
            if output.links:
                return False
        return True

    @classmethod
    def poll(cls, context):
        """Disabled for custom nodes as we do not know which nodes are supported."""
        return (nw_check(context)
                and nw_check_space_type(cls, context, 'ShaderNodeTree', 'CompositorNodeTree',
                                        'TextureNodeTree', 'GeometryNodeTree')
                and context.space_data.node_tree.nodes)

    def execute(self, context):
        nodes, links = get_nodes_links(context)

        # Store selection
        selection = []
        for node in nodes:
            if node.select:
                selection.append(node.name)

        for node in nodes:
            node.select = False

        deleted_nodes = []
        temp_deleted_nodes = []
        del_unused_iterations = len(nodes)
        for it in range(0, del_unused_iterations):
            temp_deleted_nodes = list(deleted_nodes)  # keep record of last iteration
            for node in nodes:
                if self.is_unused_node(node):
                    node.select = True
                    deleted_nodes.append(node.name)
                    bpy.ops.node.delete()

            if temp_deleted_nodes == deleted_nodes:  # stop iterations when there are no more nodes to be deleted
                break

        if self.delete_frames:
            repeat = True
            while repeat:
                frames_in_use = []
                frames = []
                repeat = False
                for node in nodes:
                    if node.parent:
                        frames_in_use.append(node.parent)
                for node in nodes:
                    if node.type == 'FRAME' and node not in frames_in_use:
                        frames.append(node)
                        if node.parent:
                            repeat = True  # repeat for nested frames
                for node in frames:
                    if node not in frames_in_use:
                        node.select = True
                        deleted_nodes.append(node.name)
                bpy.ops.node.delete()

        if self.delete_muted:
            for node in nodes:
                if node.mute:
                    node.select = True
                    deleted_nodes.append(node.name)
            bpy.ops.node.delete_reconnect()

        # get unique list of deleted nodes (iterations would count the same node more than once)
        deleted_nodes = list(set(deleted_nodes))
        for n in deleted_nodes:
            self.report({'INFO'}, "Node " + n + " deleted")
        num_deleted = len(deleted_nodes)
        n = ' node'
        if num_deleted > 1:
            n += 's'
        if num_deleted:
            self.report({'INFO'}, "Deleted " + str(num_deleted) + n)
        else:
            self.report({'INFO'}, "Nothing deleted")

        # Restore selection
        nodes, links = get_nodes_links(context)
        for node in nodes:
            if node.name in selection:
                node.select = True
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class NWSwapLinks(Operator, NWBase):
    """Swap the output connections of the two selected nodes, or two similar inputs of a single node"""
    bl_idname = 'node.nw_swap_links'
    bl_label = 'Swap Links'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return nw_check(context) and context.selected_nodes and len(context.selected_nodes) <= 2

    def execute(self, context):
        nodes, links = get_nodes_links(context)
        selected_nodes = context.selected_nodes
        n1 = selected_nodes[0]

        # Swap outputs
        if len(selected_nodes) == 2:
            n2 = selected_nodes[1]
            if n1.outputs and n2.outputs:
                n1_outputs = []
                n2_outputs = []

                out_index = 0
                for output in n1.outputs:
                    if output.links:
                        for link in output.links:
                            n1_outputs.append([out_index, link.to_socket])
                            links.remove(link)
                    out_index += 1

                out_index = 0
                for output in n2.outputs:
                    if output.links:
                        for link in output.links:
                            n2_outputs.append([out_index, link.to_socket])
                            links.remove(link)
                    out_index += 1

                for connection in n1_outputs:
                    try:
                        connect_sockets(n2.outputs[connection[0]], connection[1])
                    except:
                        self.report({'WARNING'},
                                    "Some connections have been lost due to differing numbers of output sockets")
                for connection in n2_outputs:
                    try:
                        connect_sockets(n1.outputs[connection[0]], connection[1])
                    except:
                        self.report({'WARNING'},
                                    "Some connections have been lost due to differing numbers of output sockets")
            else:
                if n1.outputs or n2.outputs:
                    self.report({'WARNING'}, "One of the nodes has no outputs!")
                else:
                    self.report({'WARNING'}, "Neither of the nodes have outputs!")

        # Swap Inputs
        elif len(selected_nodes) == 1:
            if n1.inputs and n1.inputs[0].is_multi_input:
                self.report({'WARNING'}, "Can't swap inputs of a multi input socket!")
                return {'FINISHED'}
            if n1.inputs:
                types = []
                i = 0
                for i1 in n1.inputs:
                    if i1.is_linked and not i1.is_multi_input:
                        similar_types = 0
                        for i2 in n1.inputs:
                            if i1.type == i2.type and i2.is_linked and not i2.is_multi_input:
                                similar_types += 1
                        types.append([i1, similar_types, i])
                    i += 1
                types.sort(key=lambda k: k[1], reverse=True)

                if types:
                    t = types[0]
                    if t[1] == 2:
                        for i2 in n1.inputs:
                            if t[0].type == i2.type == t[0].type and t[0] != i2 and i2.is_linked:
                                pair = [t[0], i2]
                        i1f = pair[0].links[0].from_socket
                        i1t = pair[0].links[0].to_socket
                        i2f = pair[1].links[0].from_socket
                        i2t = pair[1].links[0].to_socket
                        connect_sockets(i1f, i2t)
                        connect_sockets(i2f, i1t)
                    if t[1] == 1:
                        if len(types) == 1:
                            fs = t[0].links[0].from_socket
                            i = t[2]
                            links.remove(t[0].links[0])
                            if i + 1 == len(n1.inputs):
                                i = -1
                            i += 1
                            while n1.inputs[i].is_linked:
                                i += 1
                            connect_sockets(fs, n1.inputs[i])
                        elif len(types) == 2:
                            i1f = types[0][0].links[0].from_socket
                            i1t = types[0][0].links[0].to_socket
                            i2f = types[1][0].links[0].from_socket
                            i2t = types[1][0].links[0].to_socket
                            connect_sockets(i1f, i2t)
                            connect_sockets(i2f, i1t)

                else:
                    self.report({'WARNING'}, "This node has no input connections to swap!")
            else:
                self.report({'WARNING'}, "This node has no inputs to swap!")

        force_update(context)
        return {'FINISHED'}


class NWResetBG(Operator, NWBase):
    """Reset the zoom and position of the background image"""
    bl_idname = 'node.nw_bg_reset'
    bl_label = 'Reset Backdrop'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (nw_check(context)
                and nw_check_space_type(cls, context, 'CompositorNodeTree'))

    def execute(self, context):
        context.space_data.backdrop_zoom = 1
        context.space_data.backdrop_offset[0] = 0
        context.space_data.backdrop_offset[1] = 0
        return {'FINISHED'}


class NWAddAttrNode(Operator, NWBase):
    """Add an Attribute node with this name"""
    bl_idname = 'node.nw_add_attr_node'
    bl_label = 'Add UV map'
    bl_options = {'REGISTER', 'UNDO'}

    attr_name: StringProperty()

    @classmethod
    def poll(cls, context):
        return (nw_check(context)
                and nw_check_space_type(cls, context, 'ShaderNodeTree'))

    def execute(self, context):
        bpy.ops.node.add_node('INVOKE_DEFAULT', use_transform=True, type="ShaderNodeAttribute")
        nodes, links = get_nodes_links(context)
        nodes.active.attribute_name = self.attr_name
        return {'FINISHED'}


class NWPreviewNode(Operator, NWBase):
    bl_idname = "node.nw_preview_node"
    bl_label = "Preview Node"
    bl_description = "Connect active node to the Node Group output or the Material Output"
    bl_options = {'REGISTER', 'UNDO'}

    # If false, the operator is not executed if the current node group happens to be a geometry nodes group.
    # This is needed because geometry nodes has its own viewer node that uses the same shortcut as in the compositor.
    run_in_geometry_nodes: BoolProperty(default=True)

    def __init__(self):
        self.shader_output_type = ""
        self.shader_output_ident = ""

    @classmethod
    def poll(cls, context):
        """Already implemented natively for compositing nodes."""
        return (nw_check(context)
                and nw_check_space_type(cls, context, 'ShaderNodeTree', 'GeometryNodeTree')
                and (not context.active_node
                     or context.active_node.type not in {"OUTPUT_MATERIAL", "OUTPUT_WORLD"}))

    @staticmethod
    def get_output_sockets(node_tree):
        return [item for item in node_tree.interface.items_tree
                if item.item_type == 'SOCKET' and item.in_out in {'OUTPUT', 'BOTH'}]

    def ensure_viewer_socket(self, node, socket_type, connect_socket=None):
        """Check if a viewer output already exists in a node group, otherwise create it"""
        if not hasattr(node, "node_tree"):
            return None

        viewer_socket = None
        output_sockets = self.get_output_sockets(node.node_tree)
        if len(output_sockets):
            for i, socket in enumerate(output_sockets):
                if is_viewer_socket(socket) and socket.socket_type == socket_type:
                    # If viewer output is already used but leads to the same socket we can still use it
                    is_used = self.is_socket_used_other_mats(socket)
                    if is_used:
                        if connect_socket is None:
                            continue
                        groupout = get_group_output_node(node.node_tree)
                        groupout_input = groupout.inputs[i]
                        links = groupout_input.links
                        if connect_socket not in [link.from_socket for link in links]:
                            continue
                        viewer_socket = socket
                        break

        if viewer_socket is None:
            # Create viewer socket
            viewer_socket = node.node_tree.interface.new_socket(
                viewer_socket_name, in_out='OUTPUT', socket_type=socket_type)
            viewer_socket.NWViewerSocket = True
        return viewer_socket

    def init_shader_variables(self, space, shader_type):
        if shader_type == 'OBJECT':
            if space.id in bpy.data.lights.values():
                self.shader_output_type = "OUTPUT_LIGHT"
                self.shader_output_ident = "ShaderNodeOutputLight"
            else:
                self.shader_output_type = "OUTPUT_MATERIAL"
                self.shader_output_ident = "ShaderNodeOutputMaterial"

        elif shader_type == 'WORLD':
            self.shader_output_type = "OUTPUT_WORLD"
            self.shader_output_ident = "ShaderNodeOutputWorld"

    @staticmethod
    def ensure_group_output(tree):
        """Check if a group output node exists, otherwise create it"""
        groupout = get_group_output_node(tree)
        if groupout is None:
            groupout = tree.nodes.new('NodeGroupOutput')
            loc_x, loc_y = get_output_location(tree)
            groupout.location.x = loc_x
            groupout.location.y = loc_y
            groupout.select = False
            # So that we don't keep on adding new group outputs
            groupout.is_active_output = True
        return groupout

    @classmethod
    def search_sockets(cls, node, sockets, index=None):
        """Recursively scan nodes for viewer sockets and store them in a list"""
        for i, input_socket in enumerate(node.inputs):
            if index and i != index:
                continue
            if len(input_socket.links):
                link = input_socket.links[0]
                next_node = link.from_node
                external_socket = link.from_socket
                if hasattr(next_node, "node_tree"):
                    for socket_index, socket in enumerate(next_node.node_tree.interface.items_tree):
                        if socket.identifier == external_socket.identifier:
                            break
                    if is_viewer_socket(socket) and socket not in sockets:
                        sockets.append(socket)
                        # continue search inside of node group but restrict socket to where we came from
                        groupout = get_group_output_node(next_node.node_tree)
                        cls.search_sockets(groupout, sockets, index=socket_index)

    @classmethod
    def scan_nodes(cls, tree, sockets):
        """Recursively get all viewer sockets in a material tree"""
        for node in tree.nodes:
            if hasattr(node, "node_tree"):
                if node.node_tree is None:
                    continue
                for socket in cls.get_output_sockets(node.node_tree):
                    if is_viewer_socket(socket) and (socket not in sockets):
                        sockets.append(socket)
                cls.scan_nodes(node.node_tree, sockets)

    @staticmethod
    def remove_socket(tree, socket):
        interface = tree.interface
        interface.remove(socket)
        interface.active_index = min(interface.active_index, len(interface.items_tree) - 1)

    def link_leads_to_used_socket(self, link):
        """Return True if link leads to a socket that is already used in this material"""
        socket = get_internal_socket(link.to_socket)
        return (socket and self.is_socket_used_active_mat(socket))

    def is_socket_used_active_mat(self, socket):
        """Ensure used sockets in active material is calculated and check given socket"""
        if not hasattr(self, "used_viewer_sockets_active_mat"):
            self.used_viewer_sockets_active_mat = []
            output_node = get_group_output_node(bpy.context.space_data.node_tree,
                                                output_node_type=self.shader_output_type)

            if output_node is not None:
                self.search_sockets(output_node, self.used_viewer_sockets_active_mat)
        return socket in self.used_viewer_sockets_active_mat

    def is_socket_used_other_mats(self, socket):
        """Ensure used sockets in other materials are calculated and check given socket"""
        if not hasattr(self, "used_viewer_sockets_other_mats"):
            self.used_viewer_sockets_other_mats = []
            for mat in bpy.data.materials:
                if mat.node_tree == bpy.context.space_data.node_tree or not hasattr(mat.node_tree, "nodes"):
                    continue
                # get viewer node
                output_node = get_group_output_node(mat.node_tree,
                                                    output_node_type=self.shader_output_type)
                if output_node is not None:
                    self.search_sockets(output_node, self.used_viewer_sockets_other_mats)
        return socket in self.used_viewer_sockets_other_mats

    def get_output_index(self, base_node_tree, nodes, output_node, socket_type, check_type=False):
        """Get the next available output socket in the active node"""
        out_i = None
        valid_outputs = []
        for i, out in enumerate(nodes.active.outputs):
            if is_visible_socket(out) and (not check_type or out.type == socket_type):
                valid_outputs.append(i)
        if valid_outputs:
            out_i = valid_outputs[0]  # Start index of node's outputs
        for i, valid_i in enumerate(valid_outputs):
            for out_link in nodes.active.outputs[valid_i].links:
                if is_viewer_link(out_link, output_node):
                    if nodes == base_node_tree.nodes or self.link_leads_to_used_socket(out_link):
                        if i < len(valid_outputs) - 1:
                            out_i = valid_outputs[i + 1]
                        else:
                            out_i = valid_outputs[0]
        return out_i

    def create_links(self, tree, link_end, active, out_i, socket_type):
        """Create links through node groups until we reach the active node"""
        while tree.nodes.active != active:
            node = tree.nodes.active
            viewer_socket = self.ensure_viewer_socket(
                node, socket_type, connect_socket=active.outputs[out_i] if node.node_tree.nodes.active == active else None)
            link_start = node.outputs[viewer_socket.identifier]
            if viewer_socket in self.delete_sockets:
                self.delete_sockets.remove(viewer_socket)
            connect_sockets(link_start, link_end)
            # Iterate
            link_end = self.ensure_group_output(node.node_tree).inputs[viewer_socket.identifier]
            tree = tree.nodes.active.node_tree
        connect_sockets(active.outputs[out_i], link_end)

    def invoke(self, context, event):
        space = context.space_data
        # Ignore operator when running in wrong context.
        if self.run_in_geometry_nodes != (space.tree_type == "GeometryNodeTree"):
            return {'PASS_THROUGH'}

        mlocx = event.mouse_region_x
        mlocy = event.mouse_region_y
        select_node = bpy.ops.node.select(location=(mlocx, mlocy), extend=False)
        if 'FINISHED' not in select_node:  # only run if mouse click is on a node
            return {'CANCELLED'}


        base_node_tree = space.node_tree
        active_tree = context.space_data.edit_tree
        nodes = active_tree.nodes
        active = nodes.active

        if not active and not any(is_visible_socket(out) for out in active.outputs):
            return {'CANCELLED'}

        # Scan through all nodes in tree including nodes inside of groups to find viewer sockets
        self.delete_sockets = []
        self.scan_nodes(base_node_tree, self.delete_sockets)

        # For geometry node trees we just connect to the group output
        if space.tree_type == "GeometryNodeTree" and active.outputs:
            socket_type = 'GEOMETRY'

            # Find (or create if needed) the output of this node tree
            output_node = self.ensure_group_output(base_node_tree)

            out_i = self.get_output_index(base_node_tree, nodes, output_node, 'GEOMETRY', check_type=True)
            # If there is no 'GEOMETRY' output type - We can't preview the node
            if out_i is None:
                return {'CANCELLED'}

            # Find an input socket of the output of type geometry
            geometry_out_index = None
            for i, inp in enumerate(output_node.inputs):
                if inp.type == socket_type:
                    geometry_out_index = i
                    break
            if geometry_out_index is None:
                # Create geometry socket
                geometry_out_socket = base_node_tree.interface.new_socket(
                    'Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry'
                )
                geometry_out_index = geometry_out_socket.index

            output_socket = output_node.inputs[geometry_out_index]

            self.create_links(base_node_tree, output_socket, active, out_i, 'NodeSocketGeometry')

        # What follows is code for the shader editor
        elif space.tree_type == "ShaderNodeTree" and active.outputs:
            shader_type = space.shader_type
            self.init_shader_variables(space, shader_type)
            socket_type = 'NodeSocketShader'

            # Get or create material_output node
            output_node = get_group_output_node(base_node_tree,
                                                output_node_type=self.shader_output_type)
            if not output_node:
                output_node = base_node_tree.nodes.new(self.shader_output_ident)
                output_node.location = get_output_location(base_node_tree)
                output_node.select = False

            out_i = self.get_output_index(base_node_tree, nodes, output_node, 'SHADER')

            materialout_index = 1 if active.outputs[out_i].name == "Volume" else 0
            output_socket = output_node.inputs[materialout_index]

            self.create_links(base_node_tree, output_socket, active, out_i, 'NodeSocketShader')

        # Delete sockets
        for socket in self.delete_sockets:
            if not self.is_socket_used_other_mats(socket):
                tree = socket.id_data
                self.remove_socket(tree, socket)

        nodes.active = active
        active.select = True
        force_update(context)
        return {'FINISHED'}


class NWFrameSelected(Operator, NWBase):
    bl_idname = "node.nw_frame_selected"
    bl_label = "Frame Selected"
    bl_description = "Add a frame node and parent the selected nodes to it"
    bl_options = {'REGISTER', 'UNDO'}

    label_prop: StringProperty(
        name='Label',
        description='The visual name of the frame node',
        default=' '
    )
    use_custom_color_prop: BoolProperty(
        name="Custom Color",
        description="Use custom color for the frame node",
        default=False
    )
    color_prop: FloatVectorProperty(
        name="Color",
        description="The color of the frame node",
        default=(0.604, 0.604, 0.604),
        min=0, max=1, step=1, precision=3,
        subtype='COLOR_GAMMA', size=3
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'label_prop')
        layout.prop(self, 'use_custom_color_prop')
        col = layout.column()
        col.active = self.use_custom_color_prop
        col.prop(self, 'color_prop', text="")

    def execute(self, context):
        nodes, links = get_nodes_links(context)
        selected = []
        for node in nodes:
            if node.select:
                selected.append(node)

        bpy.ops.node.add_node(type='NodeFrame')
        frm = nodes.active
        frm.label = self.label_prop
        frm.use_custom_color = self.use_custom_color_prop
        frm.color = self.color_prop

        for node in selected:
            node.parent = frm

        return {'FINISHED'}


class NWReloadImages(Operator):
    bl_idname = "node.nw_reload_images"
    bl_label = "Reload Images"
    bl_description = "Update all the image nodes to match their files on disk"

    @classmethod
    def poll(cls, context):
        return (nw_check(context)
                and nw_check_space_type(cls, context, 'ShaderNodeTree', 'CompositorNodeTree',
                                        'TextureNodeTree', 'GeometryNodeTree')
                and context.active_node is not None
                and any(is_visible_socket(out) for out in context.active_node.outputs))

    def execute(self, context):
        nodes, links = get_nodes_links(context)
        image_types = ["IMAGE", "TEX_IMAGE", "TEX_ENVIRONMENT", "TEXTURE"]
        num_reloaded = 0
        for node in nodes:
            if node.type in image_types:
                if node.type == "TEXTURE":
                    if node.texture:  # node has texture assigned
                        if node.texture.type in ['IMAGE', 'ENVIRONMENT_MAP']:
                            if node.texture.image:  # texture has image assigned
                                node.texture.image.reload()
                                num_reloaded += 1
                else:
                    if node.image:
                        node.image.reload()
                        num_reloaded += 1

        if num_reloaded:
            self.report({'INFO'}, "Reloaded images")
            print("Reloaded " + str(num_reloaded) + " images")
            force_update(context)
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No images found to reload in this node tree")
            return {'CANCELLED'}


class NWMergeNodes(Operator, NWBase):
    bl_idname = "node.nw_merge_nodes"
    bl_label = "Merge Nodes"
    bl_description = "Merge Selected Nodes"
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(
        name="mode",
        description="All possible blend types, boolean operations and math operations",
        items=blend_types + [op for op in geo_combine_operations if op not in blend_types] + [op for op in operations if op not in blend_types],
    )
    merge_type: EnumProperty(
        name="merge type",
        description="Type of Merge to be used",
        items=(
            ('AUTO', 'Auto', 'Automatic Output Type Detection'),
            ('SHADER', 'Shader', 'Merge using ADD or MIX Shader'),
            ('GEOMETRY', 'Geometry', 'Merge using Mesh Boolean or Join Geometry Node'),
            ('MIX', 'Mix Node', 'Merge using Mix Nodes'),
            ('MATH', 'Math Node', 'Merge using Math Nodes'),
            ('ZCOMBINE', 'Z-Combine Node', 'Merge using Z-Combine Nodes'),
            ('ALPHAOVER', 'Alpha Over Node', 'Merge using Alpha Over Nodes'),
        ),
    )

    # Check if the link connects to a node that is in selected_nodes
    # If not, then check recursively for each link in the nodes outputs.
    # If yes, return True. If the recursion stops without finding a node
    # in selected_nodes, it returns False. The depth is used to prevent
    # getting stuck in a loop because of an already present cycle.
    @staticmethod
    def link_creates_cycle(link, selected_nodes, depth=0) -> bool:
        if depth > 255:
            # We're stuck in a cycle, but that cycle was already present,
            # so we return False.
            # NOTE: The number 255 is arbitrary, but seems to work well.
            return False
        node = link.to_node
        if node in selected_nodes:
            return True
        if not node.outputs:
            return False
        for output in node.outputs:
            if output.is_linked:
                for olink in output.links:
                    if NWMergeNodes.link_creates_cycle(olink, selected_nodes, depth + 1):
                        return True
        # None of the outputs found a node in selected_nodes, so there is no cycle.
        return False

    # Merge the nodes in `nodes_list` with a node of type `node_name` that has a multi_input socket.
    # The parameters `socket_indices` gives the indices of the node sockets in the order that they should
    # be connected. The last one is assumed to be a multi input socket.
    # For convenience the node is returned.
    @staticmethod
    def merge_with_multi_input(nodes_list, merge_position, do_hide, loc_x, links, nodes, node_name, socket_indices):
        # The y-location of the last node
        loc_y = nodes_list[-1][2]
        if merge_position == 'CENTER':
            # Average the y-location
            for i in range(len(nodes_list) - 1):
                loc_y += nodes_list[i][2]
            loc_y = loc_y / len(nodes_list)
        new_node = nodes.new(node_name)
        new_node.hide = do_hide
        new_node.location.x = loc_x
        new_node.location.y = loc_y
        selected_nodes = [nodes[node_info[0]] for node_info in nodes_list]
        prev_links = []
        outputs_for_multi_input = []
        for i, node in enumerate(selected_nodes):
            node.select = False
            # Search for the first node which had output links that do not create
            # a cycle, which we can then reconnect afterwards.
            if prev_links == [] and node.outputs[0].is_linked:
                prev_links = [
                    link for link in node.outputs[0].links if not NWMergeNodes.link_creates_cycle(
                        link, selected_nodes)]
            # Get the index of the socket, the last one is a multi input, and is thus used repeatedly
            # To get the placement to look right we need to reverse the order in which we connect the
            # outputs to the multi input socket.
            if i < len(socket_indices) - 1:
                ind = socket_indices[i]
                connect_sockets(node.outputs[0], new_node.inputs[ind])
            else:
                outputs_for_multi_input.insert(0, node.outputs[0])
        if outputs_for_multi_input != []:
            ind = socket_indices[-1]
            for output in outputs_for_multi_input:
                connect_sockets(output, new_node.inputs[ind])
        if prev_links != []:
            for link in prev_links:
                connect_sockets(new_node.outputs[0], link.to_node.inputs[0])
        return new_node

    @classmethod
    def poll(cls, context):
        return (nw_check(context)
                and nw_check_space_type(cls, context, 'ShaderNodeTree', 'CompositorNodeTree',
                                        'TextureNodeTree', 'GeometryNodeTree'))

    def execute(self, context):
        settings = context.preferences.addons[__package__].preferences
        merge_hide = settings.merge_hide
        merge_position = settings.merge_position  # 'center' or 'bottom'

        do_hide = False
        do_hide_shader = False
        if merge_hide == 'ALWAYS':
            do_hide = True
            do_hide_shader = True
        elif merge_hide == 'NON_SHADER':
            do_hide = True

        tree_type = context.space_data.node_tree.type
        if tree_type == 'GEOMETRY':
            node_type = 'GeometryNode'
        if tree_type == 'COMPOSITING':
            node_type = 'CompositorNode'
        elif tree_type == 'SHADER':
            node_type = 'ShaderNode'
        elif tree_type == 'TEXTURE':
            node_type = 'TextureNode'
        nodes, links = get_nodes_links(context)
        mode = self.mode
        merge_type = self.merge_type
        # Prevent trying to add Z-Combine in not 'COMPOSITING' node tree.
        # 'ZCOMBINE' works only if mode == 'MIX'
        # Setting mode to None prevents trying to add 'ZCOMBINE' node.
        if (merge_type == 'ZCOMBINE' or merge_type == 'ALPHAOVER') and tree_type != 'COMPOSITING':
            merge_type = 'MIX'
            mode = 'MIX'
        if (merge_type != 'MATH' and merge_type != 'GEOMETRY') and tree_type == 'GEOMETRY':
            merge_type = 'AUTO'
        # The Mix node and math nodes used for geometry nodes are of type 'ShaderNode'
        if (merge_type == 'MATH' or merge_type == 'MIX') and tree_type == 'GEOMETRY':
            node_type = 'ShaderNode'
        selected_mix = []  # entry = [index, loc]
        selected_shader = []  # entry = [index, loc]
        selected_geometry = []  # entry = [index, loc]
        selected_math = []  # entry = [index, loc]
        selected_vector = []  # entry = [index, loc]
        selected_z = []  # entry = [index, loc]
        selected_alphaover = []  # entry = [index, loc]

        for i, node in enumerate(nodes):
            if node.select and node.outputs:
                if merge_type == 'AUTO':
                    for (type, types_list, dst) in (
                            ('SHADER', ('MIX', 'ADD'), selected_shader),
                            ('GEOMETRY', [t[0] for t in geo_combine_operations], selected_geometry),
                            ('RGBA', [t[0] for t in blend_types], selected_mix),
                            ('VALUE', [t[0] for t in operations], selected_math),
                            ('VECTOR', [], selected_vector),
                    ):
                        output = get_first_enabled_output(node)
                        output_type = output.type
                        valid_mode = mode in types_list
                        # When mode is 'MIX' we have to cheat since the mix node is not used in
                        # geometry nodes.
                        if tree_type == 'GEOMETRY':
                            if mode == 'MIX':
                                if output_type == 'VALUE' and type == 'VALUE':
                                    valid_mode = True
                                elif output_type == 'VECTOR' and type == 'VECTOR':
                                    valid_mode = True
                                elif type == 'GEOMETRY':
                                    valid_mode = True
                        # When mode is 'MIX' use mix node for both 'RGBA' and 'VALUE' output types.
                        # Cheat that output type is 'RGBA',
                        # and that 'MIX' exists in math operations list.
                        # This way when selected_mix list is analyzed:
                        # Node data will be appended even though it doesn't meet requirements.
                        elif output_type != 'SHADER' and mode == 'MIX':
                            output_type = 'RGBA'
                            valid_mode = True
                        if output_type == type and valid_mode:
                            dst.append([i, node.location.x, node.location.y, node.dimensions.x, node.hide])
                else:
                    for (type, types_list, dst) in (
                            ('SHADER', ('MIX', 'ADD'), selected_shader),
                            ('GEOMETRY', [t[0] for t in geo_combine_operations], selected_geometry),
                            ('MIX', [t[0] for t in blend_types], selected_mix),
                            ('MATH', [t[0] for t in operations], selected_math),
                            ('ZCOMBINE', ('MIX', ), selected_z),
                            ('ALPHAOVER', ('MIX', ), selected_alphaover),
                    ):
                        if merge_type == type and mode in types_list:
                            dst.append([i, node.location.x, node.location.y, node.dimensions.x, node.hide])
        # When nodes with output kinds 'RGBA' and 'VALUE' are selected at the same time
        # use only 'Mix' nodes for merging.
        # For that we add selected_math list to selected_mix list and clear selected_math.
        if selected_mix and selected_math and merge_type == 'AUTO':
            selected_mix += selected_math
            selected_math = []

        # If no nodes are selected, do nothing and pass through.
        if not (selected_mix + selected_shader + selected_geometry + selected_math
                + selected_vector + selected_z + selected_alphaover):
            return {'PASS_THROUGH'}

        for nodes_list in [
                selected_mix,
                selected_shader,
                selected_geometry,
                selected_math,
                selected_vector,
                selected_z,
                selected_alphaover]:
            if not nodes_list:
                continue
            count_before = len(nodes)
            # sort list by loc_x - reversed
            nodes_list.sort(key=lambda k: k[1], reverse=True)
            # get maximum loc_x
            loc_x = nodes_list[0][1] + nodes_list[0][3] + 70
            nodes_list.sort(key=lambda k: k[2], reverse=True)

            # Change the node type for math nodes in a geometry node tree.
            if tree_type == 'GEOMETRY':
                if nodes_list is selected_math or nodes_list is selected_vector or nodes_list is selected_mix:
                    node_type = 'ShaderNode'
                    if mode == 'MIX':
                        mode = 'ADD'
                else:
                    node_type = 'GeometryNode'
            if merge_position == 'CENTER':
                # average yloc of last two nodes (lowest two)
                loc_y = ((nodes_list[len(nodes_list) - 1][2]) + (nodes_list[len(nodes_list) - 2][2])) / 2
                if nodes_list[len(nodes_list) - 1][-1]:  # if last node is hidden, mix should be shifted up a bit
                    if do_hide:
                        loc_y += 40
                    else:
                        loc_y += 80
            else:
                loc_y = nodes_list[len(nodes_list) - 1][2]
            offset_y = 100
            if not do_hide:
                offset_y = 200
            if nodes_list == selected_shader and not do_hide_shader:
                offset_y = 150.0
            the_range = len(nodes_list) - 1
            if len(nodes_list) == 1:
                the_range = 1
            was_multi = False
            for i in range(the_range):
                if nodes_list == selected_mix:
                    mix_name = 'Mix'
                    if tree_type == 'COMPOSITING':
                        mix_name = 'MixRGB'
                    add_type = node_type + mix_name
                    add = nodes.new(add_type)
                    if tree_type != 'COMPOSITING':
                        add.data_type = 'RGBA'
                    add.blend_type = mode
                    if mode != 'MIX':
                        add.inputs[0].default_value = 1.0
                    add.show_preview = False
                    add.hide = do_hide
                    if do_hide:
                        loc_y = loc_y - 50
                    first = 6
                    second = 7
                    if tree_type == 'COMPOSITING':
                        first = 1
                        second = 2
                elif nodes_list == selected_math:
                    add_type = node_type + 'Math'
                    add = nodes.new(add_type)
                    add.operation = mode
                    add.hide = do_hide
                    if do_hide:
                        loc_y = loc_y - 50
                    first = 0
                    second = 1
                elif nodes_list == selected_shader:
                    if mode == 'MIX':
                        add_type = node_type + 'MixShader'
                        add = nodes.new(add_type)
                        add.hide = do_hide_shader
                        if do_hide_shader:
                            loc_y = loc_y - 50
                        first = 1
                        second = 2
                    elif mode == 'ADD':
                        add_type = node_type + 'AddShader'
                        add = nodes.new(add_type)
                        add.hide = do_hide_shader
                        if do_hide_shader:
                            loc_y = loc_y - 50
                        first = 0
                        second = 1
                elif nodes_list == selected_geometry:
                    if mode in ('JOIN', 'MIX'):
                        add_type = node_type + 'JoinGeometry'
                        add = self.merge_with_multi_input(
                            nodes_list, merge_position, do_hide, loc_x, links, nodes, add_type, [0])
                    else:
                        add_type = node_type + 'MeshBoolean'
                        indices = [0, 1] if mode == 'DIFFERENCE' else [1]
                        add = self.merge_with_multi_input(
                            nodes_list, merge_position, do_hide, loc_x, links, nodes, add_type, indices)
                        add.operation = mode
                    was_multi = True
                    break
                elif nodes_list == selected_vector:
                    add_type = node_type + 'VectorMath'
                    add = nodes.new(add_type)
                    add.operation = mode
                    add.hide = do_hide
                    if do_hide:
                        loc_y = loc_y - 50
                    first = 0
                    second = 1
                elif nodes_list == selected_z:
                    add = nodes.new('CompositorNodeZcombine')
                    add.show_preview = False
                    add.hide = do_hide
                    if do_hide:
                        loc_y = loc_y - 50
                    first = 0
                    second = 2
                elif nodes_list == selected_alphaover:
                    add = nodes.new('CompositorNodeAlphaOver')
                    add.show_preview = False
                    add.hide = do_hide
                    if do_hide:
                        loc_y = loc_y - 50
                    first = 1
                    second = 2
                add.location = loc_x, loc_y
                loc_y += offset_y
                add.select = True

            # This has already been handled separately
            if was_multi:
                continue
            count_adds = i + 1
            count_after = len(nodes)
            index = count_after - 1
            first_selected = nodes[nodes_list[0][0]]
            # "last" node has been added as first, so its index is count_before.
            last_add = nodes[count_before]
            # Create list of invalid indexes.
            invalid_nodes = [nodes[n[0]]
                             for n in (selected_mix + selected_math + selected_shader + selected_z + selected_geometry)]

            # Special case:
            # Two nodes were selected and first selected has no output links, second selected has output links.
            # Then add links from last add to all links 'to_socket' of out links of second selected.
            first_selected_output = get_first_enabled_output(first_selected)
            if len(nodes_list) == 2:
                if not first_selected_output.links:
                    second_selected = nodes[nodes_list[1][0]]
                    for ss_link in get_first_enabled_output(second_selected).links:
                        # Prevent cyclic dependencies when nodes to be merged are linked to one another.
                        # Link only if "to_node" index not in invalid indexes list.
                        if not self.link_creates_cycle(ss_link, invalid_nodes):
                            connect_sockets(get_first_enabled_output(last_add), ss_link.to_socket)
            # add links from last_add to all links 'to_socket' of out links of first selected.
            for fs_link in first_selected_output.links:
                # Link only if "to_node" index not in invalid indexes list.
                if not self.link_creates_cycle(fs_link, invalid_nodes):
                    connect_sockets(get_first_enabled_output(last_add), fs_link.to_socket)
            # add link from "first" selected and "first" add node
            node_to = nodes[count_after - 1]
            connect_sockets(first_selected_output, node_to.inputs[first])
            if node_to.type == 'ZCOMBINE':
                for fs_out in first_selected.outputs:
                    if fs_out != first_selected_output and fs_out.name in ('Z', 'Depth'):
                        connect_sockets(fs_out, node_to.inputs[1])
                        break
            # add links between added ADD nodes and between selected and ADD nodes
            for i in range(count_adds):
                if i < count_adds - 1:
                    node_from = nodes[index]
                    node_to = nodes[index - 1]
                    node_to_input_i = first
                    node_to_z_i = 1  # if z combine - link z to first z input
                    connect_sockets(get_first_enabled_output(node_from), node_to.inputs[node_to_input_i])
                    if node_to.type == 'ZCOMBINE':
                        for from_out in node_from.outputs:
                            if from_out != get_first_enabled_output(node_from) and from_out.name in ('Z', 'Depth'):
                                connect_sockets(from_out, node_to.inputs[node_to_z_i])
                if len(nodes_list) > 1:
                    node_from = nodes[nodes_list[i + 1][0]]
                    node_to = nodes[index]
                    node_to_input_i = second
                    node_to_z_i = 3  # if z combine - link z to second z input
                    connect_sockets(get_first_enabled_output(node_from), node_to.inputs[node_to_input_i])
                    if node_to.type == 'ZCOMBINE':
                        for from_out in node_from.outputs:
                            if from_out != get_first_enabled_output(node_from) and from_out.name in ('Z', 'Depth'):
                                connect_sockets(from_out, node_to.inputs[node_to_z_i])
                index -= 1
            # set "last" of added nodes as active
            nodes.active = last_add
            for i, x, y, dx, h in nodes_list:
                nodes[i].select = False

        return {'FINISHED'}


class NWBatchChangeNodes(Operator, NWBase):
    bl_idname = "node.nw_batch_change"
    bl_label = "Batch Change"
    bl_description = "Batch Change Blend Type and Math Operation"
    bl_options = {'REGISTER', 'UNDO'}

    blend_type: EnumProperty(
        name="Blend Type",
        items=blend_types + navs,
    )
    operation: EnumProperty(
        name="Operation",
        items=operations + navs,
    )

    @classmethod
    def poll(cls, context):
        return (nw_check(context)
                and nw_check_space_type(cls, context, 'ShaderNodeTree', 'CompositorNodeTree',
                                        'TextureNodeTree', 'GeometryNodeTree'))

    def execute(self, context):
        blend_type = self.blend_type
        operation = self.operation
        for node in context.selected_nodes:
            if node.type == 'MIX_RGB' or (node.bl_idname == 'ShaderNodeMix' and node.data_type == 'RGBA'):
                if blend_type not in [nav[0] for nav in navs]:
                    node.blend_type = blend_type
                else:
                    if blend_type == 'NEXT':
                        index = [i for i, entry in enumerate(blend_types) if node.blend_type in entry][0]
                        # index = blend_types.index(node.blend_type)
                        if index == len(blend_types) - 1:
                            node.blend_type = blend_types[0][0]
                        else:
                            node.blend_type = blend_types[index + 1][0]

                    if blend_type == 'PREV':
                        index = [i for i, entry in enumerate(blend_types) if node.blend_type in entry][0]
                        if index == 0:
                            node.blend_type = blend_types[len(blend_types) - 1][0]
                        else:
                            node.blend_type = blend_types[index - 1][0]

            if node.type == 'MATH' or node.bl_idname == 'ShaderNodeMath':
                if operation not in [nav[0] for nav in navs]:
                    node.operation = operation
                else:
                    if operation == 'NEXT':
                        index = [i for i, entry in enumerate(operations) if node.operation in entry][0]
                        # index = operations.index(node.operation)
                        if index == len(operations) - 1:
                            node.operation = operations[0][0]
                        else:
                            node.operation = operations[index + 1][0]

                    if operation == 'PREV':
                        index = [i for i, entry in enumerate(operations) if node.operation in entry][0]
                        # index = operations.index(node.operation)
                        if index == 0:
                            node.operation = operations[len(operations) - 1][0]
                        else:
                            node.operation = operations[index - 1][0]

        return {'FINISHED'}


class NWChangeMixFactor(Operator, NWBase):
    bl_idname = "node.nw_factor"
    bl_label = "Change Factor"
    bl_description = "Change Factors of Mix Nodes and Mix Shader Nodes"
    bl_options = {'REGISTER', 'UNDO'}

    # option: Change factor.
    # If option is 1.0 or 0.0 - set to 1.0 or 0.0
    # Else - change factor by option value.
    option: FloatProperty()

    def execute(self, context):
        nodes, links = get_nodes_links(context)
        option = self.option
        selected = []  # entry = index
        for si, node in enumerate(nodes):
            if node.select:
                if node.type in {'MIX_RGB', 'MIX_SHADER'} or node.bl_idname == 'ShaderNodeMix':
                    selected.append(si)

        for si in selected:
            fac = nodes[si].inputs[0]
            nodes[si].hide = False
            if option in {0.0, 1.0}:
                fac.default_value = option
            else:
                fac.default_value += option

        return {'FINISHED'}


class NWCopySettings(Operator, NWBase):
    bl_idname = "node.nw_copy_settings"
    bl_label = "Copy Settings"
    bl_description = "Copy Settings of Active Node to Selected Nodes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (nw_check(context)
                and context.active_node is not None
                and context.active_node.type != 'FRAME')

    def execute(self, context):
        node_active = context.active_node
        node_selected = context.selected_nodes

        # Error handling
        if not (len(node_selected) > 1):
            self.report({'ERROR'}, "2 nodes must be selected at least")
            return {'CANCELLED'}

        # Check if active node is in the selection
        selected_node_names = [n.name for n in node_selected]
        if node_active.name not in selected_node_names:
            self.report({'ERROR'}, "No active node")
            return {'CANCELLED'}

        # Get nodes in selection by type
        valid_nodes = [n for n in node_selected if n.type == node_active.type]

        if not (len(valid_nodes) > 1) and node_active:
            self.report({'ERROR'}, "Selected nodes are not of the same type as {}".format(node_active.name))
            return {'CANCELLED'}

        if len(valid_nodes) != len(node_selected):
            # Report nodes that are not valid
            valid_node_names = [n.name for n in valid_nodes]
            not_valid_names = list(set(selected_node_names) - set(valid_node_names))
            self.report(
                {'INFO'},
                "Ignored {} (not of the same type as {})".format(
                    ", ".join(not_valid_names),
                    node_active.name))

        # Reference original
        orig = node_active
        # node_selected_names = [n.name for n in node_selected]

        # Output list
        success_names = []

        # Deselect all nodes
        for i in node_selected:
            i.select = False

        # Code by zeffii from http://blender.stackexchange.com/a/42338/3710
        # Run through all other nodes
        for node in valid_nodes[1:]:

            # Check for frame node
            parent = node.parent if node.parent else None
            node_loc = [node.location.x, node.location.y]

            # Select original to duplicate
            orig.select = True

            # Duplicate selected node
            bpy.ops.node.duplicate()
            new_node = context.selected_nodes[0]

            # Deselect copy
            new_node.select = False

            # Properties to copy
            node_tree = node.id_data
            props_to_copy = 'bl_idname name location height width'.split(' ')

            # Input and outputs
            reconnections = []
            mappings = chain.from_iterable([node.inputs, node.outputs])
            for i in (i for i in mappings if i.is_linked):
                for L in i.links:
                    reconnections.append([L.from_socket.path_from_id(), L.to_socket.path_from_id()])

            # Properties
            props = {j: getattr(node, j) for j in props_to_copy}
            props_to_copy.pop(0)

            for prop in props_to_copy:
                setattr(new_node, prop, props[prop])

            # Get the node tree to remove the old node
            nodes = node_tree.nodes
            nodes.remove(node)
            new_node.name = props['name']

            if parent:
                new_node.parent = parent
                new_node.location = node_loc

            for str_from, str_to in reconnections:
                node_tree.connect_sockets(eval(str_from), eval(str_to))

            success_names.append(new_node.name)

        orig.select = True
        node_tree.nodes.active = orig
        self.report(
            {'INFO'},
            "Successfully copied attributes from {} to: {}".format(
                orig.name,
                ", ".join(success_names)))
        return {'FINISHED'}


class NWCopyLabel(Operator, NWBase):
    bl_idname = "node.nw_copy_label"
    bl_label = "Copy Label"
    bl_options = {'REGISTER', 'UNDO'}

    option: EnumProperty(
        name="option",
        description="Source of name of label",
        items=(
            ('FROM_ACTIVE', 'from active', 'from active node',),
            ('FROM_NODE', 'from node', 'from node linked to selected node'),
            ('FROM_SOCKET', 'from socket', 'from socket linked to selected node'),
        )
    )

    def execute(self, context):
        nodes, links = get_nodes_links(context)
        option = self.option
        active = nodes.active
        if option == 'FROM_ACTIVE':
            if active:
                src_label = active.label
                for node in [n for n in nodes if n.select and nodes.active != n]:
                    node.label = src_label
        elif option == 'FROM_NODE':
            selected = [n for n in nodes if n.select]
            for node in selected:
                for input in node.inputs:
                    if input.links:
                        src = input.links[0].from_node
                        node.label = src.label
                        break
        elif option == 'FROM_SOCKET':
            selected = [n for n in nodes if n.select]
            for node in selected:
                for input in node.inputs:
                    if input.links:
                        src = input.links[0].from_socket
                        node.label = src.name
                        break

        return {'FINISHED'}


class NWClearLabel(Operator, NWBase):
    bl_idname = "node.nw_clear_label"
    bl_label = "Clear Label"
    bl_options = {'REGISTER', 'UNDO'}

    option: BoolProperty()

    def execute(self, context):
        nodes, links = get_nodes_links(context)
        for node in [n for n in nodes if n.select]:
            node.label = ''

        return {'FINISHED'}

    def invoke(self, context, event):
        if self.option:
            return self.execute(context)
        else:
            return context.window_manager.invoke_confirm(self, event)


class NWModifyLabels(Operator, NWBase):
    """Modify Labels of all selected nodes"""
    bl_idname = "node.nw_modify_labels"
    bl_label = "Modify Labels"
    bl_options = {'REGISTER', 'UNDO'}

    prepend: StringProperty(
        name="Add to Beginning"
    )
    append: StringProperty(
        name="Add to End"
    )
    replace_from: StringProperty(
        name="Text to Replace"
    )
    replace_to: StringProperty(
        name="Replace with"
    )

    def execute(self, context):
        nodes, links = get_nodes_links(context)
        for node in [n for n in nodes if n.select]:
            node.label = self.prepend + node.label.replace(self.replace_from, self.replace_to) + self.append

        return {'FINISHED'}

    def invoke(self, context, event):
        self.prepend = ""
        self.append = ""
        self.remove = ""
        return context.window_manager.invoke_props_dialog(self)


class NWAddTextureSetup(Operator, NWBase):
    bl_idname = "node.nw_add_texture"
    bl_label = "Texture Setup"
    bl_description = "Add Texture Node Setup to Selected Shaders"
    bl_options = {'REGISTER', 'UNDO'}

    add_mapping: BoolProperty(
        name="Add Mapping Nodes",
        description="Create coordinate and mapping nodes for the texture (ignored for selected texture nodes)",
        default=True)

    @classmethod
    def poll(cls, context):
        return (nw_check(context)
                and nw_check_space_type(cls, context, 'ShaderNodeTree'))

    def execute(self, context):
        nodes, links = get_nodes_links(context)

        texture_types = get_texture_node_types()
        selected_nodes = [n for n in nodes if n.select]

        for node in selected_nodes:
            if not node.inputs:
                continue

            input_index = 0
            target_input = node.inputs[0]
            for input in node.inputs:
                if input.enabled:
                    input_index += 1
                    if not input.is_linked:
                        target_input = input
                        break
            else:
                self.report({'WARNING'}, "No free inputs for node: " + node.name)
                continue

            x_offset = 0
            padding = 40.0
            locx = node.location.x
            locy = node.location.y - (input_index * padding)

            is_texture_node = node.rna_type.identifier in texture_types
            use_environment_texture = node.type == 'BACKGROUND'

            # Add an image texture before normal shader nodes.
            if not is_texture_node:
                image_texture_type = 'ShaderNodeTexEnvironment' if use_environment_texture else 'ShaderNodeTexImage'
                image_texture_node = nodes.new(image_texture_type)
                x_offset = x_offset + image_texture_node.width + padding
                image_texture_node.location = [locx - x_offset, locy]
                nodes.active = image_texture_node
                connect_sockets(image_texture_node.outputs[0], target_input)

                # The mapping setup following this will connect to the first input of this image texture.
                target_input = image_texture_node.inputs[0]

            node.select = False

            if is_texture_node or self.add_mapping:
                # Add Mapping node.
                mapping_node = nodes.new('ShaderNodeMapping')
                x_offset = x_offset + mapping_node.width + padding
                mapping_node.location = [locx - x_offset, locy]
                connect_sockets(mapping_node.outputs[0], target_input)

                # Add Texture Coordinates node.
                tex_coord_node = nodes.new('ShaderNodeTexCoord')
                x_offset = x_offset + tex_coord_node.width + padding
                tex_coord_node.location = [locx - x_offset, locy]

                is_procedural_texture = is_texture_node and node.type != 'TEX_IMAGE'
                use_generated_coordinates = is_procedural_texture or use_environment_texture
                tex_coord_output = tex_coord_node.outputs[0 if use_generated_coordinates else 2]
                connect_sockets(tex_coord_output, mapping_node.inputs[0])

        return {'FINISHED'}


class NWAddPrincipledSetup(Operator, NWBase, ImportHelper):
    bl_idname = "node.nw_add_textures_for_principled"
    bl_label = "Principled Texture Setup"
    bl_description = "Add Texture Node Setup for Principled BSDF"
    bl_options = {'REGISTER', 'UNDO'}

    directory: StringProperty(
        name='Directory',
        subtype='DIR_PATH',
        default='',
        description='Folder to search in for image files'
    )
    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    relative_path: BoolProperty(
        name='Relative Path',
        description='Set the file path relative to the blend file, when possible',
        default=True
    )

    order = [
        "filepath",
        "files",
    ]

    def draw(self, context):
        layout = self.layout
        layout.alignment = 'LEFT'

        layout.prop(self, 'relative_path')

    @classmethod
    def poll(cls, context):
        return (nw_check(context)
                and nw_check_space_type(cls, context, 'ShaderNodeTree'))

    def execute(self, context):
        # Check if everything is ok
        if not self.directory:
            self.report({'INFO'}, 'No Folder Selected')
            return {'CANCELLED'}
        if not self.files[:]:
            self.report({'INFO'}, 'No Files Selected')
            return {'CANCELLED'}

        nodes, links = get_nodes_links(context)
        active_node = nodes.active
        if not (active_node and active_node.bl_idname == 'ShaderNodeBsdfPrincipled'):
            self.report({'INFO'}, 'Select Principled BSDF')
            return {'CANCELLED'}

        # Filter textures names for texturetypes in filenames
        # [Socket Name, [abbreviations and keyword list], Filename placeholder]
        tags = context.preferences.addons[__package__].preferences.principled_tags
        normal_abbr = tags.normal.split(' ')
        bump_abbr = tags.bump.split(' ')
        gloss_abbr = tags.gloss.split(' ')
        rough_abbr = tags.rough.split(' ')
        socketnames = [
            ['Displacement', tags.displacement.split(' '), None],
            ['Base Color', tags.base_color.split(' '), None],
            ['Metallic', tags.metallic.split(' '), None],
            ['Specular IOR Level', tags.specular.split(' '), None],
            ['Roughness', rough_abbr + gloss_abbr, None],
            ['Normal', normal_abbr + bump_abbr, None],
            ['Transmission Weight', tags.transmission.split(' '), None],
            ['Emission Color', tags.emission.split(' '), None],
            ['Alpha', tags.alpha.split(' '), None],
            ['Ambient Occlusion', tags.ambient_occlusion.split(' '), None],
        ]

        match_files_to_socket_names(self.files, socketnames)
        # Remove socketnames without found files
        socketnames = [s for s in socketnames if s[2]
                       and path.exists(self.directory + s[2])]
        if not socketnames:
            self.report({'INFO'}, 'No matching images found')
            print('No matching images found')
            return {'CANCELLED'}

        # Don't override path earlier as os.path is used to check the absolute path
        import_path = self.directory
        if self.relative_path:
            if bpy.data.filepath:
                try:
                    import_path = bpy.path.relpath(self.directory)
                except ValueError:
                    pass

        # Add found images
        print('\nMatched Textures:')
        texture_nodes = []
        disp_texture = None
        ao_texture = None
        normal_node = None
        roughness_node = None
        for i, sname in enumerate(socketnames):
            print(i, sname[0], sname[2])

            # DISPLACEMENT NODES
            if sname[0] == 'Displacement':
                disp_texture = nodes.new(type='ShaderNodeTexImage')
                img = bpy.data.images.load(path.join(import_path, sname[2]))
                disp_texture.image = img
                disp_texture.label = 'Displacement'
                if disp_texture.image:
                    disp_texture.image.colorspace_settings.is_data = True

                # Add displacement offset nodes
                disp_node = nodes.new(type='ShaderNodeDisplacement')
                # Align the Displacement node under the active Principled BSDF node
                disp_node.location = active_node.location + Vector((100, -700))
                link = connect_sockets(disp_node.inputs[0], disp_texture.outputs[0])

                # TODO Turn on true displacement in the material
                # Too complicated for now

                # Find output node
                output_node = [n for n in nodes if n.bl_idname == 'ShaderNodeOutputMaterial']
                if output_node:
                    if not output_node[0].inputs[2].is_linked:
                        link = connect_sockets(output_node[0].inputs[2], disp_node.outputs[0])

                continue

            # AMBIENT OCCLUSION TEXTURE
            if sname[0] == 'Ambient Occlusion':
                ao_texture = nodes.new(type='ShaderNodeTexImage')
                img = bpy.data.images.load(path.join(import_path, sname[2]))
                ao_texture.image = img
                ao_texture.label = sname[0]
                if ao_texture.image:
                    ao_texture.image.colorspace_settings.is_data = True

                continue

            if not active_node.inputs[sname[0]].is_linked:
                # No texture node connected -> add texture node with new image
                texture_node = nodes.new(type='ShaderNodeTexImage')
                img = bpy.data.images.load(path.join(import_path, sname[2]))
                texture_node.image = img

                # NORMAL NODES
                if sname[0] == 'Normal':
                    # Test if new texture node is normal or bump map
                    fname_components = split_into_components(sname[2])
                    match_normal = set(normal_abbr).intersection(set(fname_components))
                    match_bump = set(bump_abbr).intersection(set(fname_components))
                    if match_normal:
                        # If Normal add normal node in between
                        normal_node = nodes.new(type='ShaderNodeNormalMap')
                        link = connect_sockets(normal_node.inputs[1], texture_node.outputs[0])
                    elif match_bump:
                        # If Bump add bump node in between
                        normal_node = nodes.new(type='ShaderNodeBump')
                        link = connect_sockets(normal_node.inputs[2], texture_node.outputs[0])

                    link = connect_sockets(active_node.inputs[sname[0]], normal_node.outputs[0])
                    normal_node_texture = texture_node

                elif sname[0] == 'Roughness':
                    # Test if glossy or roughness map
                    fname_components = split_into_components(sname[2])
                    match_rough = set(rough_abbr).intersection(set(fname_components))
                    match_gloss = set(gloss_abbr).intersection(set(fname_components))

                    if match_rough:
                        # If Roughness nothing to to
                        link = connect_sockets(active_node.inputs[sname[0]], texture_node.outputs[0])

                    elif match_gloss:
                        # If Gloss Map add invert node
                        invert_node = nodes.new(type='ShaderNodeInvert')
                        link = connect_sockets(invert_node.inputs[1], texture_node.outputs[0])

                        link = connect_sockets(active_node.inputs[sname[0]], invert_node.outputs[0])
                        roughness_node = texture_node

                else:
                    # This is a simple connection Texture --> Input slot
                    link = connect_sockets(active_node.inputs[sname[0]], texture_node.outputs[0])

                # Use non-color except for color inputs
                if sname[0] not in ['Base Color', 'Emission Color'] and texture_node.image:
                    texture_node.image.colorspace_settings.is_data = True

            else:
                # If already texture connected. add to node list for alignment
                texture_node = active_node.inputs[sname[0]].links[0].from_node

            # This are all connected texture nodes
            texture_nodes.append(texture_node)
            texture_node.label = sname[0]

        if disp_texture:
            texture_nodes.append(disp_texture)

        if ao_texture:
            # We want the ambient occlusion texture to be the top most texture node
            texture_nodes.insert(0, ao_texture)

        # Alignment
        for i, texture_node in enumerate(texture_nodes):
            offset = Vector((-550, (i * -280) + 200))
            texture_node.location = active_node.location + offset

        if normal_node:
            # Extra alignment if normal node was added
            normal_node.location = normal_node_texture.location + Vector((300, 0))

        if roughness_node:
            # Alignment of invert node if glossy map
            invert_node.location = roughness_node.location + Vector((300, 0))

        # Add texture input + mapping
        mapping = nodes.new(type='ShaderNodeMapping')
        mapping.location = active_node.location + Vector((-1050, 0))
        if len(texture_nodes) > 1:
            # If more than one texture add reroute node in between
            reroute = nodes.new(type='NodeReroute')
            texture_nodes.append(reroute)
            tex_coords = Vector((texture_nodes[0].location.x,
                                 sum(n.location.y for n in texture_nodes) / len(texture_nodes)))
            reroute.location = tex_coords + Vector((-50, -120))
            for texture_node in texture_nodes:
                link = connect_sockets(texture_node.inputs[0], reroute.outputs[0])
            link = connect_sockets(reroute.inputs[0], mapping.outputs[0])
        else:
            link = connect_sockets(texture_nodes[0].inputs[0], mapping.outputs[0])

        # Connect texture_coordiantes to mapping node
        texture_input = nodes.new(type='ShaderNodeTexCoord')
        texture_input.location = mapping.location + Vector((-200, 0))
        link = connect_sockets(mapping.inputs[0], texture_input.outputs[2])

        # Create frame around tex coords and mapping
        frame = nodes.new(type='NodeFrame')
        frame.label = 'Mapping'
        mapping.parent = frame
        texture_input.parent = frame
        frame.update()

        # Create frame around texture nodes
        frame = nodes.new(type='NodeFrame')
        frame.label = 'Textures'
        for tnode in texture_nodes:
            tnode.parent = frame
        frame.update()

        # Just to be sure
        active_node.select = False
        nodes.update()
        links.update()
        force_update(context)
        return {'FINISHED'}


class NWAddReroutes(Operator, NWBase):
    """Add Reroute Nodes and link them to outputs of selected nodes"""
    bl_idname = "node.nw_add_reroutes"
    bl_label = "Add Reroutes"
    bl_description = "Add Reroutes to Outputs"
    bl_options = {'REGISTER', 'UNDO'}

    option: EnumProperty(
        name="option",
        items=[
            ('ALL', 'to all', 'Add to all outputs'),
            ('LOOSE', 'to loose', 'Add only to loose outputs'),
            ('LINKED', 'to linked', 'Add only to linked outputs'),
        ]
    )

    def execute(self, context):
        tree_type = context.space_data.node_tree.type
        option = self.option
        nodes, links = get_nodes_links(context)
        # output valid when option is 'all' or when 'loose' output has no links
        valid = False
        post_select = []  # nodes to be selected after execution
        # create reroutes and recreate links
        for node in [n for n in nodes if n.select]:
            if node.outputs:
                x = node.location.x
                y = node.location.y
                width = node.width
                # unhide 'REROUTE' nodes to avoid issues with location.y
                if node.type == 'REROUTE':
                    node.hide = False
                # Hack needed to calculate real width
                if node.hide:
                    bpy.ops.node.select_all(action='DESELECT')
                    helper = nodes.new('NodeReroute')
                    helper.select = True
                    node.select = True
                    # resize node and helper to zero. Then check locations to calculate width
                    bpy.ops.transform.resize(value=(0.0, 0.0, 0.0))
                    width = 2.0 * (helper.location.x - node.location.x)
                    # restore node location
                    node.location = x, y
                    # delete helper
                    node.select = False
                    # only helper is selected now
                    bpy.ops.node.delete()
                x = node.location.x + width + 20.0
                if node.type != 'REROUTE':
                    y -= 35.0
                y_offset = -22.0
                loc = x, y
            reroutes_count = 0  # will be used when aligning reroutes added to hidden nodes
            for out_i, output in enumerate(node.outputs):
                pass_used = False  # initial value to be analyzed if 'R_LAYERS'
                # if node != 'R_LAYERS' - "pass_used" not needed, so set it to True
                if node.type != 'R_LAYERS':
                    pass_used = True
                else:  # if 'R_LAYERS' check if output represent used render pass
                    node_scene = node.scene
                    node_layer = node.layer
                    # If output - "Alpha" is analyzed - assume it's used. Not represented in passes.
                    if output.name == 'Alpha':
                        pass_used = True
                    else:
                        # check entries in global 'rl_outputs' variable
                        for rlo in rl_outputs:
                            if output.name in {rlo.output_name, rlo.exr_output_name}:
                                pass_used = getattr(node_scene.view_layers[node_layer], rlo.render_pass)
                                break
                if pass_used:
                    valid = ((option == 'ALL') or
                             (option == 'LOOSE' and not output.links) or
                             (option == 'LINKED' and output.links))
                    # Add reroutes only if valid, but offset location in all cases.
                    if valid:
                        n = nodes.new('NodeReroute')
                        nodes.active = n
                        for link in output.links:
                            connect_sockets(n.outputs[0], link.to_socket)
                        connect_sockets(output, n.inputs[0])
                        n.location = loc
                        post_select.append(n)
                    reroutes_count += 1
                    y += y_offset
                    loc = x, y
            # disselect the node so that after execution of script only newly created nodes are selected
            node.select = False
            # nicer reroutes distribution along y when node.hide
            if node.hide:
                y_translate = reroutes_count * y_offset / 2.0 - y_offset - 35.0
                for reroute in [r for r in nodes if r.select]:
                    reroute.location.y -= y_translate
            for node in post_select:
                node.select = True

        return {'FINISHED'}


class NWLinkActiveToSelected(Operator, NWBase):
    """Link active node to selected nodes basing on various criteria"""
    bl_idname = "node.nw_link_active_to_selected"
    bl_label = "Link Active Node to Selected"
    bl_options = {'REGISTER', 'UNDO'}

    replace: BoolProperty()
    use_node_name: BoolProperty()
    use_outputs_names: BoolProperty()

    @classmethod
    def poll(cls, context):
        return (nw_check(context)
                and context.active_node is not None
                and context.active_node.select)

    def execute(self, context):
        nodes, links = get_nodes_links(context)
        replace = self.replace
        use_node_name = self.use_node_name
        use_outputs_names = self.use_outputs_names
        active = nodes.active
        selected = [node for node in nodes if node.select and node != active]
        outputs = []  # Only usable outputs of active nodes will be stored here.
        for out in active.outputs:
            if active.type != 'R_LAYERS':
                outputs.append(out)
            else:
                # 'R_LAYERS' node type needs special handling.
                # outputs of 'R_LAYERS' are callable even if not seen in UI.
                # Only outputs that represent used passes should be taken into account
                # Check if pass represented by output is used.
                # global 'rl_outputs' list will be used for that
                for rlo in rl_outputs:
                    pass_used = False  # initial value. Will be set to True if pass is used
                    if out.name == 'Alpha':
                        # Alpha output is always present. Doesn't have representation in render pass. Assume it's used.
                        pass_used = True
                    elif out.name in {rlo.output_name, rlo.exr_output_name}:
                        # example 'render_pass' entry: 'use_pass_uv' Check if True in scene render layers
                        pass_used = getattr(active.scene.view_layers[active.layer], rlo.render_pass)
                        break
                if pass_used:
                    outputs.append(out)
        doit = True  # Will be changed to False when links successfully added to previous output.
        for out in outputs:
            if doit:
                for node in selected:
                    dst_name = node.name  # Will be compared with src_name if needed.
                    # When node has label - use it as dst_name
                    if node.label:
                        dst_name = node.label
                    valid = True  # Initial value. Will be changed to False if names don't match.
                    src_name = dst_name  # If names not used - this assignment will keep valid = True.
                    if use_node_name:
                        # Set src_name to source node name or label
                        src_name = active.name
                        if active.label:
                            src_name = active.label
                    elif use_outputs_names:
                        src_name = (out.name, )
                        for rlo in rl_outputs:
                            if out.name in {rlo.output_name, rlo.exr_output_name}:
                                src_name = (rlo.output_name, rlo.exr_output_name)
                    if dst_name not in src_name:
                        valid = False
                    if valid:
                        for input in node.inputs:
                            if input.type == out.type or node.type == 'REROUTE':
                                if replace or not input.is_linked:
                                    connect_sockets(out, input)
                                    if not use_node_name and not use_outputs_names:
                                        doit = False
                                    break

        return {'FINISHED'}


class NWAlignNodes(Operator, NWBase):
    '''Align the selected nodes neatly in a row/column'''
    bl_idname = "node.nw_align_nodes"
    bl_label = "Align Nodes"
    bl_options = {'REGISTER', 'UNDO'}
    margin: IntProperty(name='Margin', default=50, description='The amount of space between nodes')

    def execute(self, context):
        nodes, links = get_nodes_links(context)
        margin = self.margin

        selection = []
        for node in nodes:
            if node.select and node.type != 'FRAME':
                selection.append(node)

        # If no nodes are selected, align all nodes
        active_loc = None
        if not selection:
            selection = nodes
        elif nodes.active in selection:
            active_loc = copy(nodes.active.location)  # make a copy, not a reference

        # Check if nodes should be laid out horizontally or vertically
        # use dimension to get center of node, not corner
        x_locs = [n.location.x + (n.dimensions.x / 2) for n in selection]
        y_locs = [n.location.y - (n.dimensions.y / 2) for n in selection]
        x_range = max(x_locs) - min(x_locs)
        y_range = max(y_locs) - min(y_locs)
        mid_x = (max(x_locs) + min(x_locs)) / 2
        mid_y = (max(y_locs) + min(y_locs)) / 2
        horizontal = x_range > y_range

        # Sort selection by location of node mid-point
        if horizontal:
            selection = sorted(selection, key=lambda n: n.location.x + (n.dimensions.x / 2))
        else:
            selection = sorted(selection, key=lambda n: n.location.y - (n.dimensions.y / 2), reverse=True)

        # Alignment
        current_pos = 0
        for node in selection:
            current_margin = margin
            current_margin = current_margin * 0.5 if node.hide else current_margin  # use a smaller margin for hidden nodes

            if horizontal:
                node.location.x = current_pos
                current_pos += current_margin + node.dimensions.x
                node.location.y = mid_y + (node.dimensions.y / 2)
            else:
                node.location.y = current_pos
                current_pos -= (current_margin * 0.3) + node.dimensions.y  # use half-margin for vertical alignment
                node.location.x = mid_x - (node.dimensions.x / 2)

        # If active node is selected, center nodes around it
        if active_loc is not None:
            active_loc_diff = active_loc - nodes.active.location
            for node in selection:
                node.location += active_loc_diff
        else:  # Position nodes centered around where they used to be
            locs = ([n.location.x + (n.dimensions.x / 2) for n in selection]
                    ) if horizontal else ([n.location.y - (n.dimensions.y / 2) for n in selection])
            new_mid = (max(locs) + min(locs)) / 2
            for node in selection:
                if horizontal:
                    node.location.x += (mid_x - new_mid)
                else:
                    node.location.y += (mid_y - new_mid)

        return {'FINISHED'}


class NWSelectParentChildren(Operator, NWBase):
    bl_idname = "node.nw_select_parent_child"
    bl_label = "Select Parent or Children"
    bl_options = {'REGISTER', 'UNDO'}

    option: EnumProperty(
        name="option",
        items=(
            ('PARENT', 'Select Parent', 'Select Parent Frame'),
            ('CHILD', 'Select Children', 'Select members of selected frame'),
        )
    )

    def execute(self, context):
        nodes, links = get_nodes_links(context)
        option = self.option
        selected = [node for node in nodes if node.select]
        if option == 'PARENT':
            for sel in selected:
                parent = sel.parent
                if parent:
                    parent.select = True
        else:  # option == 'CHILD'
            for sel in selected:
                children = [node for node in nodes if node.parent == sel]
                for kid in children:
                    kid.select = True

        return {'FINISHED'}


class NWDetachOutputs(Operator, NWBase):
    """Detach outputs of selected node leaving inputs linked"""
    bl_idname = "node.nw_detach_outputs"
    bl_label = "Detach Outputs"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        nodes, links = get_nodes_links(context)
        selected = context.selected_nodes
        bpy.ops.node.duplicate_move_keep_inputs()
        new_nodes = context.selected_nodes
        bpy.ops.node.select_all(action="DESELECT")
        for node in selected:
            node.select = True
        bpy.ops.node.delete_reconnect()
        for new_node in new_nodes:
            new_node.select = True
        bpy.ops.transform.translate('INVOKE_DEFAULT')

        return {'FINISHED'}


class NWLinkToOutputNode(Operator):
    """Link to Composite node or Material Output node"""
    bl_idname = "node.nw_link_out"
    bl_label = "Connect to Output"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """Disabled for custom nodes as we do not know which nodes are outputs."""
        return (nw_check(context)
                and nw_check_space_type(cls, context, 'ShaderNodeTree', 'CompositorNodeTree',
                                        'TextureNodeTree', 'GeometryNodeTree')
                and context.active_node is not None
                and any(is_visible_socket(out) for out in context.active_node.outputs))

    def execute(self, context):
        nodes, links = get_nodes_links(context)
        active = nodes.active
        output_index = None
        tree_type = context.space_data.tree_type
        shader_outputs = {'OBJECT': 'ShaderNodeOutputMaterial',
                          'WORLD': 'ShaderNodeOutputWorld',
                          'LINESTYLE': 'ShaderNodeOutputLineStyle'}
        output_type = {
            'ShaderNodeTree': shader_outputs[context.space_data.shader_type],
            'CompositorNodeTree': 'CompositorNodeComposite',
            'TextureNodeTree': 'TextureNodeOutput',
            'GeometryNodeTree': 'NodeGroupOutput',
        }[tree_type]
        for node in nodes:
            # check whether the node is an output node and,
            # if supported, whether it's the active one
            if node.rna_type.identifier == output_type \
               and (node.is_active_output if hasattr(node, 'is_active_output')
                    else True):
                output_node = node
                break
        else:  # No output node exists
            bpy.ops.node.select_all(action="DESELECT")
            output_node = nodes.new(output_type)
            output_node.location.x = active.location.x + active.dimensions.x + 80
            output_node.location.y = active.location.y

        if active.outputs:
            for i, output in enumerate(active.outputs):
                if is_visible_socket(output):
                    output_index = i
                    break
            for i, output in enumerate(active.outputs):
                if output.type == output_node.inputs[0].type and is_visible_socket(output):
                    output_index = i
                    break

            out_input_index = 0
            if tree_type == 'ShaderNodeTree':
                if active.outputs[output_index].name == 'Volume':
                    out_input_index = 1
                elif active.outputs[output_index].name == 'Displacement':
                    out_input_index = 2
            elif tree_type == 'GeometryNodeTree':
                if active.outputs[output_index].type != 'GEOMETRY':
                    return {'CANCELLED'}
            connect_sockets(active.outputs[output_index], output_node.inputs[out_input_index])

        force_update(context)  # viewport render does not update

        return {'FINISHED'}


class NWMakeLink(Operator, NWBase):
    """Make a link from one socket to another"""
    bl_idname = 'node.nw_make_link'
    bl_label = 'Make Link'
    bl_options = {'REGISTER', 'UNDO'}
    from_socket: IntProperty()
    to_socket: IntProperty()

    def execute(self, context):
        nodes, links = get_nodes_links(context)

        n1 = nodes[context.scene.NWLazySource]
        n2 = nodes[context.scene.NWLazyTarget]

        connect_sockets(n1.outputs[self.from_socket], n2.inputs[self.to_socket])

        force_update(context)

        return {'FINISHED'}


class NWCallInputsMenu(Operator, NWBase):
    """Link from this output"""
    bl_idname = 'node.nw_call_inputs_menu'
    bl_label = 'Make Link'
    bl_options = {'REGISTER', 'UNDO'}
    from_socket: IntProperty()

    def execute(self, context):
        nodes, links = get_nodes_links(context)

        context.scene.NWSourceSocket = self.from_socket

        n1 = nodes[context.scene.NWLazySource]
        n2 = nodes[context.scene.NWLazyTarget]
        if len(n2.inputs) > 1:
            bpy.ops.wm.call_menu("INVOKE_DEFAULT", name=NWConnectionListInputs.bl_idname)
        elif len(n2.inputs) == 1:
            connect_sockets(n1.outputs[self.from_socket], n2.inputs[0])
        return {'FINISHED'}


class NWAddSequence(Operator, NWBase, ImportHelper):
    """Add an Image Sequence"""
    bl_idname = 'node.nw_add_sequence'
    bl_label = 'Import Image Sequence'
    bl_options = {'REGISTER', 'UNDO'}

    directory: StringProperty(
        subtype="DIR_PATH"
    )
    filename: StringProperty(
        subtype="FILE_NAME"
    )
    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'}
    )
    relative_path: BoolProperty(
        name='Relative Path',
        description='Set the file path relative to the blend file, when possible',
        default=True
    )

    def draw(self, context):
        layout = self.layout
        layout.alignment = 'LEFT'

        layout.prop(self, 'relative_path')

    def execute(self, context):
        nodes, links = get_nodes_links(context)
        directory = self.directory
        filename = self.filename
        files = self.files
        tree = context.space_data.node_tree

        # DEBUG
        # print ("\nDIR:", directory)
        # print ("FN:", filename)
        # print ("Fs:", list(f.name for f in files), '\n')

        if tree.type == 'SHADER':
            node_type = "ShaderNodeTexImage"
        elif tree.type == 'COMPOSITING':
            node_type = "CompositorNodeImage"
        else:
            self.report({'ERROR'}, "Unsupported Node Tree type!")
            return {'CANCELLED'}

        if not files[0].name and not filename:
            self.report({'ERROR'}, "No file chosen")
            return {'CANCELLED'}
        elif files[0].name and (not filename or not path.exists(directory + filename)):
            # User has selected multiple files without an active one, or the active one is non-existent
            filename = files[0].name

        if not path.exists(directory + filename):
            self.report({'ERROR'}, filename + " does not exist!")
            return {'CANCELLED'}

        without_ext = '.'.join(filename.split('.')[:-1])

        # if last digit isn't a number, it's not a sequence
        if not without_ext[-1].isdigit():
            self.report({'ERROR'}, filename + " does not seem to be part of a sequence")
            return {'CANCELLED'}

        extension = filename.split('.')[-1]
        reverse = without_ext[::-1]  # reverse string

        count_numbers = 0
        for char in reverse:
            if char.isdigit():
                count_numbers += 1
            else:
                break

        without_num = without_ext[:count_numbers * -1]

        files = sorted(glob(directory + without_num + "[0-9]" * count_numbers + "." + extension))

        num_frames = len(files)

        nodes_list = [node for node in nodes]
        if nodes_list:
            nodes_list.sort(key=lambda k: k.location.x)
            xloc = nodes_list[0].location.x - 220  # place new nodes at far left
            yloc = 0
            for node in nodes:
                node.select = False
                yloc += node_mid_pt(node, 'y')
            yloc = yloc / len(nodes)
        else:
            xloc = 0
            yloc = 0

        name_with_hashes = without_num + "#" * count_numbers + '.' + extension

        bpy.ops.node.add_node('INVOKE_DEFAULT', use_transform=True, type=node_type)
        node = nodes.active
        node.label = name_with_hashes

        filepath = directory + (without_ext + '.' + extension)
        if self.relative_path:
            if bpy.data.filepath:
                try:
                    filepath = bpy.path.relpath(filepath)
                except ValueError:
                    pass

        img = bpy.data.images.load(filepath)
        img.source = 'SEQUENCE'
        img.name = name_with_hashes
        node.image = img
        image_user = node.image_user if tree.type == 'SHADER' else node
        # separate the number from the file name of the first  file
        image_user.frame_offset = int(files[0][len(without_num) + len(directory):-1 * (len(extension) + 1)]) - 1
        image_user.frame_duration = num_frames

        return {'FINISHED'}


class NWAddMultipleImages(Operator, NWBase, ImportHelper):
    """Add multiple images at once"""
    bl_idname = 'node.nw_add_multiple_images'
    bl_label = 'Open Selected Images'
    bl_options = {'REGISTER', 'UNDO'}
    directory: StringProperty(
        subtype="DIR_PATH"
    )
    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    def execute(self, context):
        nodes, links = get_nodes_links(context)

        xloc, yloc = context.region.view2d.region_to_view(context.area.width / 2, context.area.height / 2)

        if context.space_data.node_tree.type == 'SHADER':
            node_type = "ShaderNodeTexImage"
        elif context.space_data.node_tree.type == 'COMPOSITING':
            node_type = "CompositorNodeImage"
        else:
            self.report({'ERROR'}, "Unsupported Node Tree type!")
            return {'CANCELLED'}

        new_nodes = []
        for f in self.files:
            fname = f.name

            node = nodes.new(node_type)
            new_nodes.append(node)
            node.label = fname
            node.hide = True
            node.location.x = xloc
            node.location.y = yloc
            yloc -= 40

            img = bpy.data.images.load(self.directory + fname)
            node.image = img

        # shift new nodes up to center of tree
        list_size = new_nodes[0].location.y - new_nodes[-1].location.y
        for node in nodes:
            if node in new_nodes:
                node.select = True
                node.location.y += (list_size / 2)
            else:
                node.select = False
        return {'FINISHED'}


class NWViewerFocus(bpy.types.Operator):
    """Set the viewer tile center to the mouse position"""
    bl_idname = "node.nw_viewer_focus"
    bl_label = "Viewer Focus"

    x: bpy.props.IntProperty()
    y: bpy.props.IntProperty()

    @classmethod
    def poll(cls, context):
        return (nw_check(context)
                and nw_check_space_type(cls, context, 'CompositorNodeTree'))

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        render = context.scene.render
        space = context.space_data
        percent = render.resolution_percentage * 0.01

        nodes, links = get_nodes_links(context)
        viewers = [n for n in nodes if n.type == 'VIEWER']

        if viewers:
            mlocx = event.mouse_region_x
            mlocy = event.mouse_region_y
            select_node = bpy.ops.node.select(location=(mlocx, mlocy), extend=False)

            if 'FINISHED' not in select_node:  # only run if we're not clicking on a node
                region_x = context.region.width
                region_y = context.region.height

                region_center_x = context.region.width / 2
                region_center_y = context.region.height / 2

                bd_x = render.resolution_x * percent * space.backdrop_zoom
                bd_y = render.resolution_y * percent * space.backdrop_zoom

                backdrop_center_x = (bd_x / 2) - space.backdrop_offset[0]
                backdrop_center_y = (bd_y / 2) - space.backdrop_offset[1]

                margin_x = region_center_x - backdrop_center_x
                margin_y = region_center_y - backdrop_center_y

                abs_mouse_x = (mlocx - margin_x) / bd_x
                abs_mouse_y = (mlocy - margin_y) / bd_y

                for node in viewers:
                    node.center_x = abs_mouse_x
                    node.center_y = abs_mouse_y
            else:
                return {'PASS_THROUGH'}

        return self.execute(context)


class NWSaveViewer(bpy.types.Operator, ExportHelper):
    """Save the current viewer node to an image file"""
    bl_idname = "node.nw_save_viewer"
    bl_label = "Save This Image"
    filepath: StringProperty(subtype="FILE_PATH")
    filename_ext: EnumProperty(
        name="Format",
        description="Choose the file format to save to",
        items=(('.bmp', "BMP", ""),
               ('.rgb', 'IRIS', ""),
               ('.png', 'PNG', ""),
               ('.jpg', 'JPEG', ""),
               ('.jp2', 'JPEG2000', ""),
               ('.tga', 'TARGA', ""),
               ('.cin', 'CINEON', ""),
               ('.dpx', 'DPX', ""),
               ('.exr', 'OPEN_EXR', ""),
               ('.hdr', 'HDR', ""),
               ('.tif', 'TIFF', "")),
        default='.png',
    )

    @classmethod
    def poll(cls, context):
        return (nw_check(context)
                and nw_check_space_type(cls, context, 'CompositorNodeTree')
                and any(img.source == 'VIEWER'
                        and img.render_slots == 0
                        for img in bpy.data.images)
                and sum(bpy.data.images["Viewer Node"].size) > 0)  # False if not connected or connected but no image

    def execute(self, context):
        fp = self.filepath
        if fp:
            formats = {
                '.bmp': 'BMP',
                '.rgb': 'IRIS',
                '.png': 'PNG',
                '.jpg': 'JPEG',
                '.jpeg': 'JPEG',
                '.jp2': 'JPEG2000',
                '.tga': 'TARGA',
                '.cin': 'CINEON',
                '.dpx': 'DPX',
                '.exr': 'OPEN_EXR',
                '.hdr': 'HDR',
                '.tiff': 'TIFF',
                '.tif': 'TIFF'}
            basename, ext = path.splitext(fp)
            old_render_format = context.scene.render.image_settings.file_format
            context.scene.render.image_settings.file_format = formats[self.filename_ext]
            context.area.type = "IMAGE_EDITOR"
            context.area.spaces[0].image = bpy.data.images['Viewer Node']
            context.area.spaces[0].image.save_render(fp)
            context.area.type = "NODE_EDITOR"
            context.scene.render.image_settings.file_format = old_render_format
            return {'FINISHED'}


class NWResetNodes(bpy.types.Operator):
    """Reset Nodes in Selection"""
    bl_idname = "node.nw_reset_nodes"
    bl_label = "Reset Nodes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return space.type == 'NODE_EDITOR'

    def execute(self, context):
        node_active = context.active_node
        node_selected = context.selected_nodes
        node_ignore = ["FRAME", "REROUTE", "GROUP", "SIMULATION_INPUT", "SIMULATION_OUTPUT"]

        # Check if one node is selected at least
        if not (len(node_selected) > 0):
            self.report({'ERROR'}, "1 node must be selected at least")
            return {'CANCELLED'}

        active_node_name = node_active.name if node_active.select else None
        valid_nodes = [n for n in node_selected if n.type not in node_ignore]

        # Create output lists
        selected_node_names = [n.name for n in node_selected]
        success_names = []

        # Reset all valid children in a frame
        node_active_is_frame = False
        if len(node_selected) == 1 and node_active.type == "FRAME":
            node_tree = node_active.id_data
            children = [n for n in node_tree.nodes if n.parent == node_active]
            if children:
                valid_nodes = [n for n in children if n.type not in node_ignore]
                selected_node_names = [n.name for n in children if n.type not in node_ignore]
                node_active_is_frame = True

        # Check if valid nodes in selection
        if not (len(valid_nodes) > 0):
            # Check for frames only
            frames_selected = [n for n in node_selected if n.type == "FRAME"]
            if (len(frames_selected) > 1 and len(frames_selected) == len(node_selected)):
                self.report({'ERROR'}, "Please select only 1 frame to reset")
            else:
                self.report({'ERROR'}, "No valid node(s) in selection")
            return {'CANCELLED'}

        # Report nodes that are not valid
        if len(valid_nodes) != len(node_selected) and node_active_is_frame is False:
            valid_node_names = [n.name for n in valid_nodes]
            not_valid_names = list(set(selected_node_names) - set(valid_node_names))
            self.report({'INFO'}, "Ignored {}".format(", ".join(not_valid_names)))

        # Deselect all nodes
        for i in node_selected:
            i.select = False

        # Run through all valid nodes
        for node in valid_nodes:

            parent = node.parent if node.parent else None
            node_loc = [node.location.x, node.location.y]

            node_tree = node.id_data
            props_to_copy = 'bl_idname name location height width'.split(' ')

            reconnections = []
            mappings = chain.from_iterable([node.inputs, node.outputs])
            for i in (i for i in mappings if i.is_linked):
                for L in i.links:
                    reconnections.append([L.from_socket.path_from_id(), L.to_socket.path_from_id()])

            props = {j: getattr(node, j) for j in props_to_copy}

            new_node = node_tree.nodes.new(props['bl_idname'])
            props_to_copy.pop(0)

            for prop in props_to_copy:
                setattr(new_node, prop, props[prop])

            nodes = node_tree.nodes
            nodes.remove(node)
            new_node.name = props['name']

            if parent:
                new_node.parent = parent
                new_node.location = node_loc

            for str_from, str_to in reconnections:
                connect_sockets(eval(str_from), eval(str_to))

            new_node.select = False
            success_names.append(new_node.name)

        # Reselect all nodes
        if selected_node_names and node_active_is_frame is False:
            for i in selected_node_names:
                node_tree.nodes[i].select = True

        if active_node_name is not None:
            node_tree.nodes[active_node_name].select = True
            node_tree.nodes.active = node_tree.nodes[active_node_name]

        self.report({'INFO'}, "Successfully reset {}".format(", ".join(success_names)))
        return {'FINISHED'}


classes = (
    NWLazyMix,
    NWLazyConnect,
    NWDeleteUnused,
    NWSwapLinks,
    NWResetBG,
    NWAddAttrNode,
    NWPreviewNode,
    NWFrameSelected,
    NWReloadImages,
    NWMergeNodes,
    NWBatchChangeNodes,
    NWChangeMixFactor,
    NWCopySettings,
    NWCopyLabel,
    NWClearLabel,
    NWModifyLabels,
    NWAddTextureSetup,
    NWAddPrincipledSetup,
    NWAddReroutes,
    NWLinkActiveToSelected,
    NWAlignNodes,
    NWSelectParentChildren,
    NWDetachOutputs,
    NWLinkToOutputNode,
    NWMakeLink,
    NWCallInputsMenu,
    NWAddSequence,
    NWAddMultipleImages,
    NWViewerFocus,
    NWSaveViewer,
    NWResetNodes,
)


def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)


def unregister():
    from bpy.utils import unregister_class

    for cls in classes:
        unregister_class(cls)
