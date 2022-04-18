import bpy


class BOOSTER_PT_node_transfer(bpy.types.Panel):
    """Panel for copying and pasting nodes between shader and geometry nodes"""
    bl_idname = "BOOSTER_PT_node_transfer"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_context = "scene"
    bl_category = "BB"
    bl_label = "Node Transfer"

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator("scene.booster_copy_nodes")
        row.operator("scene.booster_paste_nodes")