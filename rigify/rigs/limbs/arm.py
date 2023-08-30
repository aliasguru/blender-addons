# SPDX-FileCopyrightText: 2016-2022 Blender Foundation
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy

from mathutils import Matrix

from ...utils.bones import put_bone, compute_chain_x_axis, align_bone_x_axis, align_bone_z_axis
from ...utils.naming import make_derived_name
from ...utils.widgets import adjust_widget_transform_mesh

from ..widgets import create_hand_widget
from ...utils.widgets_basic import create_circle_widget

from ...base_rig import stage

from .limb_rigs import BaseLimbRig


class Rig(BaseLimbRig):
    """Human arm rig."""

    min_valid_orgs = max_valid_orgs = 3

    make_wrist_pivot: bool

    def initialize(self):
        super().initialize()
        self.make_wrist_pivot = self.params.make_ik_wrist_pivot

    def prepare_bones(self):
        orgs = self.bones.org.main

        if self.params.rotation_axis == 'automatic':
            axis = compute_chain_x_axis(self.obj, orgs[0:2])

            for bone in orgs:
                align_bone_x_axis(self.obj, bone, axis)

        elif self.params.auto_align_extremity:
            axis = self.vector_without_z(self.get_bone(orgs[2]).z_axis)

            align_bone_z_axis(self.obj, orgs[2], axis)

    ####################################################
    # BONES

    class CtrlBones(BaseLimbRig.CtrlBones):
        ik_wrist: str                  # Wrist pivot control (if enabled)

    class MchBones(BaseLimbRig.MchBones):
        ik_wrist: str                  # Wrist pivot control output (if enabled)

    bones: BaseLimbRig.ToplevelBones[
        'Rig.OrgBones',
        'Rig.CtrlBones',
        'Rig.MchBones',
        list[str]
    ]

    ####################################################
    # Overrides

    def register_switch_parents(self, pbuilder):
        super().register_switch_parents(pbuilder)

        pbuilder.register_parent(self, self.bones.org.main[2], exclude_self=True, tags={'limb_end'})

    def make_ik_ctrl_widget(self, ctrl):
        create_hand_widget(self.obj, ctrl)

    ####################################################
    # Palm Pivot

    def get_ik_input_bone(self):
        if self.make_wrist_pivot:
            return self.bones.mch.ik_wrist
        else:
            return self.get_ik_control_output()

    def get_extra_ik_controls(self):
        controls = super().get_extra_ik_controls()
        if self.make_wrist_pivot:
            controls += [self.bones.ctrl.ik_wrist]
        return controls

    @stage.generate_bones
    def make_wrist_pivot_control(self):
        if self.make_wrist_pivot:
            org = self.bones.org.main[2]
            self.bones.ctrl.ik_wrist = self.make_wrist_pivot_bone(org)
            self.bones.mch.ik_wrist = self.copy_bone(org, make_derived_name(org, 'mch', '_ik_wrist'), scale=0.25)

    def make_wrist_pivot_bone(self, org):
        name = self.copy_bone(org, make_derived_name(org, 'ctrl', '_ik_wrist'), scale=0.5)
        put_bone(self.obj, name, self.get_bone(org).tail)
        return name

    @stage.parent_bones
    def parent_wrist_pivot_control(self):
        if self.make_wrist_pivot:
            ctrl = self.bones.ctrl.ik_wrist
            self.set_bone_parent(ctrl, self.get_ik_control_output())
            self.set_bone_parent(self.bones.mch.ik_wrist, ctrl)

    @stage.generate_widgets
    def make_wrist_pivot_widget(self):
        if self.make_wrist_pivot:
            ctrl = self.bones.ctrl.ik_wrist

            if self.main_axis == 'x':
                obj = create_circle_widget(self.obj, ctrl, head_tail=-0.3, head_tail_x=0.5)
            else:
                obj = create_circle_widget(self.obj, ctrl, head_tail=0.5, head_tail_x=-0.3)

            if obj:
                org_bone = self.get_bone(self.bones.org.main[2])
                offset = org_bone.head - self.get_bone(ctrl).head
                adjust_widget_transform_mesh(obj, Matrix.Translation(offset))

    ####################################################
    # Settings

    @classmethod
    def add_parameters(cls, params):
        super().add_parameters(params)

        params.make_ik_wrist_pivot = bpy.props.BoolProperty(
            name="IK Wrist Pivot", default=False,
            description="Make an extra IK hand control pivoting around the tip of the hand"
        )

    @classmethod
    def parameters_ui(cls, layout, params, end='Hand'):
        layout.prop(params, "make_ik_wrist_pivot")

        super().parameters_ui(layout, params, end)


def create_sample(obj, limb=False):
    # generated by rigify.utils.write_metarig
    bpy.ops.object.mode_set(mode='EDIT')
    arm = obj.data

    bones = {}
    bone = arm.edit_bones.new('upper_arm.L')
    bone.head[:] = -0.0016, 0.0060, -0.0012
    bone.tail[:] = 0.2455, 0.0678, -0.1367
    bone.roll = 2.0724
    bone.use_connect = False
    bones['upper_arm.L'] = bone.name
    bone = arm.edit_bones.new('forearm.L')
    bone.head[:] = 0.2455, 0.0678, -0.1367
    bone.tail[:] = 0.4625, 0.0285, -0.2797
    bone.roll = 2.1535
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['upper_arm.L']]
    bones['forearm.L'] = bone.name
    bone = arm.edit_bones.new('hand.L')
    bone.head[:] = 0.4625, 0.0285, -0.2797
    bone.tail[:] = 0.5265, 0.0205, -0.3273
    bone.roll = 2.2103
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['forearm.L']]
    bones['hand.L'] = bone.name

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['upper_arm.L']]
    pbone.rigify_type = 'limbs.super_limb' if limb else 'limbs.arm'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    try:
        pbone.rigify_parameters.ik_local_location = False
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['forearm.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['hand.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'

    bpy.ops.object.mode_set(mode='EDIT')
    for bone in arm.edit_bones:
        bone.select = False
        bone.select_head = False
        bone.select_tail = False
    for b in bones:
        bone = arm.edit_bones[bones[b]]
        bone.select = True
        bone.select_head = True
        bone.select_tail = True
        arm.edit_bones.active = bone
        if bcoll := arm.collections.active:
            bcoll.assign(bone)

    return bones
