# Blender Booster Add-on
New add-on for Blender 3D to combine several improvements and functionalities.

https://user-images.githubusercontent.com/15720606/159595511-ef7f95c3-0732-46f7-a5c4-749cab026567.mp4

In the node_transfer folder is a node_groups.blend file, which contains groups for replacing nodes that don't exist in the transfer to node tree. For example there is no Texture Coordinate node in the geometry nodes,
instead I created a ShaderNodeTexCoord group which contains a Position node connected to Outputs that match the original Texture Coordinate node exactly. The name 'ShaderNodeTexCoord' is the node.bl_rna.identifier for the
Texture Coordinate node. The .blend file contains some of the common identifiers for which you can create node groups (if you do please share so I can update the main file). So it is important that the 
node groups you create are named with the identifier like the one above so that the add-on can find them and use them as replacements for nodes that cannot be transfered. Otherwise the addon creates empty node groups that
match original node for manual revision.
