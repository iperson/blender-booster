import bpy
from bpy.types import AddonPreferences
from bpy.props import BoolProperty


class BOOSTER_preferences(AddonPreferences):
    # this must match the add-on name, use '__package__'
    # when defining this in a submodule of a python package.
    bl_idname = "blender_booster"

    toggle_header_buttons_node_transfer: BoolProperty(
        name="Show in Header",
        default=True,
        description="Show buttons in the Node Editor Header instead of side bar",
    )

    def draw(self, context):
        box_transfer_node = self.layout.box()
        col = box_transfer_node.column()
        row = col.row()
        row.label(text="Node Transfer Settings:")
        row.prop(self, "toggle_header_buttons_node_transfer")