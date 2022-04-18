import bpy


bl_info = {
    "name" : "Blender Booster",
    "author" : "Valeri Barashkov",
    "description" : "",
    "blender" : (3, 2, 0),
    "version" : (0, 1, 0),
    "location" : "Either header or the right side panel under BB tab.",
    "warning" : "Requires Blender 3.2 or Fix T96909, otherwise will crash on group copy from Shader to Geometry Nodes!",
    "category" : "Generic"
}

from . import auto_load

auto_load.init()

def draw_item(self, context):
    preferences = context.preferences
    addon_prefs = preferences.addons[__name__].preferences
    
    if addon_prefs.toggle_header_buttons_node_transfer:
        layout = self.layout
        layout.operator("scene.booster_copy_nodes", icon="COPYDOWN", text="")
        layout.operator("scene.booster_paste_nodes", icon="PASTEDOWN", text="")

def register():
    auto_load.register()
    bpy.types.NODE_HT_header.append(draw_item)

def unregister():
    auto_load.unregister()
    bpy.types.NODE_HT_header.remove(draw_item)
