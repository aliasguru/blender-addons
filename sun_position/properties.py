# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from bpy.types import AddonPreferences, PropertyGroup
from bpy.props import (StringProperty, EnumProperty, IntProperty,
                       FloatProperty, BoolProperty, PointerProperty)

from .sun_calc import sun_update, parse_coordinates, surface_update, analemmas_update, sun
from .draw import north_update

from math import pi
from datetime import datetime
TODAY = datetime.today()

############################################################################
# Sun panel properties
############################################################################


class SunPosProperties(PropertyGroup):
    usage_mode: EnumProperty(
        name="Usage Mode",
        description="Operate in normal mode or environment texture mode",
        items=(
            ('NORMAL', "Normal", ""),
            ('HDR', "Sun + HDR texture", ""),
        ),
        default='NORMAL',
        update=sun_update)

    use_daylight_savings: BoolProperty(
        name="Daylight Savings",
        description="Daylight savings time adds 1 hour to standard time",
        default=False,
        update=sun_update)

    use_refraction: BoolProperty(
        name="Use Refraction",
        description="Show the apparent Sun position due to atmospheric refraction",
        default=True,
        update=sun_update)

    show_north: BoolProperty(
        name="Show North",
        description="Draw a line pointing to the north",
        default=False,
        update=north_update)

    north_offset: FloatProperty(
        name="North Offset",
        description="Rotate the scene to choose the North direction",
        unit="ROTATION",
        soft_min=-pi, soft_max=pi, step=10.0, default=0.0,
        update=sun_update)

    show_surface: BoolProperty(
        name="Show Surface",
        description="Draw the surface that the Sun occupies in the sky",
        default=False,
        update=surface_update)

    show_analemmas: BoolProperty(
        name="Show Analemmas",
        description="Draw Sun analemmas. These help visualize the motion of the Sun in the sky during the year, for each hour of the day",
        default=False,
        update=analemmas_update)

    latitude: FloatProperty(
        name="Latitude",
        description="Latitude: (+) Northern (-) Southern",
        soft_min=-90.0, soft_max=90.0,
        step=5, precision=3,
        default=0.0,
        update=sun_update)

    longitude: FloatProperty(
        name="Longitude",
        description="Longitude: (-) West of Greenwich (+) East of Greenwich",
        soft_min=-180.0, soft_max=180.0,
        step=5, precision=3,
        default=0.0,
        update=sun_update)

    sunrise_time: FloatProperty(
        name="Sunrise Time",
        description="Time at which the Sun rises",
        soft_min=0.0, soft_max=24.0,
        default=0.0,
        get=lambda _: sun.sunrise)

    sunset_time: FloatProperty(
        name="Sunset Time",
        description="Time at which the Sun sets",
        soft_min=0.0, soft_max=24.0,
        default=0.0,
        get=lambda _: sun.sunset)

    sun_azimuth: FloatProperty(
        name="Sun Azimuth",
        description="Rotation angle of the Sun from the direction of the north",
        soft_min=-pi, soft_max=pi,
        default=0.0,
        get=lambda _: sun.azimuth)

    sun_elevation: FloatProperty(
        name="Sun Elevation",
        description="Elevation angle of the Sun",
        soft_min=-pi/2, soft_max=pi/2,
        default=0.0,
        get=lambda _: sun.elevation)

    co_parser: StringProperty(
        name="Enter Coordinates",
        description="Enter coordinates from an online map",
        update=parse_coordinates)

    month: IntProperty(
        name="Month",
        min=1, max=12, default=TODAY.month,
        update=sun_update)

    day: IntProperty(
        name="Day",
        min=1, max=31, default=TODAY.day,
        update=sun_update)

    year: IntProperty(
        name="Year",
        min=1, max=4000, default=TODAY.year,
        update=sun_update)

    use_day_of_year: BoolProperty(
        description="Use a single value for the day of year",
        name="Use day of year",
        default=False,
        update=sun_update)

    day_of_year: IntProperty(
        name="Day of Year",
        min=1, max=366, default=1,
        update=sun_update)

    UTC_zone: FloatProperty(
        name="UTC Zone",
        description="Difference from Greenwich, England, in hours",
        precision=1,
        min=-14.0, max=13, step=50, default=0.0,
        update=sun_update)

    time: FloatProperty(
        name="Time",
        description="Time of the day",
        precision=4,
        soft_min=0.0, soft_max=23.9999, step=1.0, default=12.0,
        update=sun_update)

    sun_distance: FloatProperty(
        name="Distance",
        description="Distance to the Sun from the origin",
        unit="LENGTH",
        min=0.0, soft_max=3000.0, step=10.0, default=50.0,
        update=sun_update)

    sun_object: PointerProperty(
        name="Sun Object",
        type=bpy.types.Object,
        description="Sun object to use in the scene",
        poll=lambda self, obj: obj.type == 'LIGHT',
        update=sun_update)

    object_collection: PointerProperty(
        name="Collection",
        type=bpy.types.Collection,
        description="Collection of objects used to visualize the motion of the Sun",
        update=sun_update)

    object_collection_type: EnumProperty(
        name="Display type",
        description="Type of Sun motion to visualize.",
        items=(
            ('ANALEMMA', "Analemma", "Trajectory of the Sun in the sky during the year, for a given time of the day"),
            ('DIURNAL', "Diurnal", "Trajectory of the Sun in the sky during a single day"),
        ),
        default='ANALEMMA',
        update=sun_update)

    sky_texture: StringProperty(
        name="Sky Texture",
        default="",
        description="Name of the sky texture to use",
        update=sun_update)

    hdr_texture: StringProperty(
        default="Environment Texture",
        name="Environment Texture",
        description="Name of the environment texture to use. World nodes must be enabled "
                    "and the color set to an environment Texture",
        update=sun_update)

    hdr_azimuth: FloatProperty(
        name="Rotation",
        description="Rotation angle of the Sun and environment texture",
        unit="ROTATION",
        step=10.0,
        default=0.0, precision=3,
        update=sun_update)

    hdr_elevation: FloatProperty(
        name="Elevation",
        description="Elevation angle of the Sun",
        unit="ROTATION",
        step=10.0,
        default=0.0, precision=3,
        update=sun_update)

    bind_to_sun: BoolProperty(
        name="Bind Texture to Sun",
        description="If enabled, the environment texture moves with the Sun",
        default=False,
        update=sun_update)

    time_spread: FloatProperty(
        name="Time Spread",
        description="Time period around which to spread object collection",
        precision=4,
        soft_min=1.0, soft_max=24.0, step=1.0, default=23.0,
        update=sun_update)

############################################################################
# Preference panel properties
############################################################################


class SunPosAddonPreferences(AddonPreferences):
    bl_idname = __package__

    show_time_place: BoolProperty(
        name="Time and Place Presets",
        description="Show time and place presets",
        default=False)

    show_dms: BoolProperty(
        name="D° M' S\"",
        description="Show degrees, minutes, seconds labels for the latitude and longitude",
        default=True)

    show_north: BoolProperty(
        name="Show North",
        description="Show North offset choice and slider",
        default=True,
        update=sun_update)

    show_surface: BoolProperty(
        name="Show Surface",
        description="Show Sun surface choice",
        default=True,
        update=sun_update)

    show_analemmas: BoolProperty(
        name="Show Analemmas",
        description="Show Analemmas choice",
        default=True,
        update=sun_update)

    show_refraction: BoolProperty(
        name="Refraction",
        description="Show Sun Refraction choice",
        default=True,
        update=sun_update)

    show_az_el: BoolProperty(
        name="Azimuth and Elevation Info",
        description="Show azimuth and solar elevation info",
        default=True)

    show_daylight_savings: BoolProperty(
        name="Daylight Savings",
        description="Show daylight savings time choice",
        default=True,
        update=sun_update)

    show_rise_set: BoolProperty(
        name="Sunrise and Sunset Info",
        description="Show sunrise and sunset labels",
        default=True)

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        col = box.column()

        col.label(text="Show options or labels:")
        flow = col.grid_flow(columns=0, even_columns=True, even_rows=False, align=False)
        flow.prop(self, "show_time_place")
        flow.prop(self, "show_dms")
        flow.prop(self, "show_north")
        flow.prop(self, "show_surface")
        flow.prop(self, "show_analemmas")
        flow.prop(self, "show_refraction")
        flow.prop(self, "show_az_el")
        flow.prop(self, "show_daylight_savings")
        flow.prop(self, "show_rise_set")
