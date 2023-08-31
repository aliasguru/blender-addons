# SPDX-FileCopyrightText: 2018-2021 The glTF-Blender-IO authors
#
# SPDX-License-Identifier: Apache-2.0

import bpy

# Get compatibility at export with old files
def get_gltf_node_old_name():
    return "glTF Settings"

def get_gltf_node_name():
    return "glTF Material Output"

def create_settings_group(name):
    gltf_node_group = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    gltf_node_group.interface.new_socket("Occlusion", socket_type="NodeSocketFloat")
    thicknessFactor  = gltf_node_group.interface.new_socket("Thickness", socket_type="NodeSocketFloat", )
    thicknessFactor.default_value = 0.0
    gltf_node_group.nodes.new('NodeGroupOutput')
    gltf_node_group_input = gltf_node_group.nodes.new('NodeGroupInput')
    specular = gltf_node_group.interface.new_socket("Specular", socket_type="NodeSocketFloat")
    specular.default_value = 1.0
    specularColor = gltf_node_group.interface.new_socket("Specular Color", socket_type="NodeSocketColor")
    specularColor.default_value = [1.0,1.0,1.0,1.0]
    gltf_node_group_input.location = -200, 0
    return gltf_node_group
