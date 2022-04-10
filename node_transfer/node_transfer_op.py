import bpy


class BB_NodeTree():
    def __init__(self):
        self.active_nodes = {}
        self.type = ""


class BOOSTER_OT_CopyNodes(bpy.types.Operator):
    """Copy nodes from the context editor"""
    bl_idname = "scene.booster_copy_nodes"
    bl_label = "Copy Nodes"

    @classmethod
    def poll(self, context):
        if len(context.selected_nodes):
            return True

        return False

    def execute(self, context):
        # create indexes for sockets
        set_socket_index(bpy.context.space_data.node_tree)

        bpy.types.Scene.booster_src_node_tree = BB_NodeTree()
        src_nodes_tree = bpy.types.Scene.booster_src_node_tree
        src_nodes_tree.type = bpy.context.space_data.node_tree.type

        # get selected nodes and groups
        for node in context.selected_nodes:
            src_nodes_tree.active_nodes[node.name] = node

        # update Paste buttons
        for area in bpy.context.window.screen.areas:
            if area.type == 'NODE_EDITOR':
                area.tag_redraw()

        return {'FINISHED'}

def set_socket_index(node_tree):
    if node_tree == None:
        return

    for node in node_tree.nodes:
        if node.type == 'GROUP':
            set_socket_index(node.node_tree)

        for i, inp in enumerate(node.inputs):
            for lnk in inp.links:
                lnk.to_socket['index'] = i

class BOOSTER_OT_PasteNodes(bpy.types.Operator):
    """Paste nodes into the context editor"""
    bl_idname = "scene.booster_paste_nodes"
    bl_label = "Paste Nodes"

    @classmethod
    def poll(self, context):
        try:
            context.scene.booster_src_node_tree
            return True
        except:
            return False

    def execute(self, context):
        # local node group
        node_tree = context.space_data.node_tree

        # deselect all nodes
        for node in node_tree.nodes:
            node.select = False

        # source node group
        src_node_tree = context.scene.booster_src_node_tree
        transfer_nodes(node_tree, src_node_tree)
                            
        # remove temp globals
        del bpy.types.Scene.booster_src_node_tree

        return {'FINISHED'}

def transfer_nodes(node_tree, src_node_tree):
    # store transfered nodes using original node names as keys
    # this way node name changes don't cause a problem
    imported_nodes_dic = {}

    for src_node in src_node_tree.active_nodes.values():
        # handle Group node
        if src_node.type == 'GROUP':
            pasted_node = make_group_copy(node_tree, src_node)
            pasted_node['bb_type'] = 'transfer'

            # transfer nodes in group
            sub_src_node_tree = BB_NodeTree()
            for n in src_node.node_tree.nodes:
                sub_src_node_tree.active_nodes[n.name] = n
                sub_src_node_tree.type = src_node_tree.type

            transfer_nodes(pasted_node.node_tree, sub_src_node_tree)
        # handle all other nodes
        else:
            node_type = src_node.type.title()

            # handle special cases for textures
            if 'noise' in node_type.lower():
                node_type = [piece.title() for piece in node_type.split('_')]
                node_type = ''.join(node_type)

            # add new copied node or generate node if id not available
            try:
                if src_node.bl_idname == 'ShaderNodeGroup':
                    pasted_node = node_tree.nodes.new('ShaderNodeGroup')
                elif src_node.bl_idname == 'GeometryNodeGroup':
                    pasted_node = node_tree.nodes.new('GeometryNodeGroup')
                else:
                    pasted_node = node_tree.nodes.new(src_node.bl_idname)
                
                transfer_props(pasted_node, src_node)
                pasted_node['bb_type'] = 'transfer'
            except RuntimeError:
                print("BOOSTER: Cannot add node id:", src_node.bl_idname)
                # see if our blend file has a replacement node
                pasted_node = get_node_from_file(node_tree, src_node.bl_rna.identifier)
                if pasted_node == None:
                    pasted_node = make_group_from_node(node_tree, src_node)

        transfer_location(pasted_node, src_node)
        imported_nodes_dic[src_node.name] = pasted_node

    # add nodes to frames
    for src_name, src_node in src_node_tree.active_nodes.items():
        # add to frame
        if src_node.parent != None:
            frame_node = imported_nodes_dic.get(src_node.parent.name)
            node = imported_nodes_dic.get(src_name)

            if frame_node and node:
                node.parent = frame_node

    # transfer socket values
    for name, node in imported_nodes_dic.items():
        if not node:
            continue

        if node.type in ['REROUTE', 'FRAME']:
            continue

        # skip nodes that have been replaced
        if node.get('bb_type') == 'mix':
            continue

        # transfer socket values
        src_node = src_node_tree.active_nodes[name]
        for i, inp in enumerate(src_node.inputs):
            if (node.inputs[i].bl_rna.identifier not in 
            ('NodeSocketVirtual', 'NodeSocketShader', 'NodeSocketGeometry')):
                node.inputs[i].default_value = inp.default_value

    # generate links in the node tree for each added node
    for name, node in imported_nodes_dic.items():
        if node.type == 'FRAME':
            continue

        src_node = src_node_tree.active_nodes[name]

        # for each node output make new links
        for i, opt in enumerate(src_node.outputs):
            for lnk in opt.links:
                to_node = imported_nodes_dic.get(lnk.to_node.name)
                from_node = imported_nodes_dic.get(lnk.from_node.name)

                if to_node == None:
                    continue

                print("linking: {} to {}".format(name, to_node.name))

                from_socket = from_node.outputs[i]

                index = lnk.to_socket.get('index')
                to_socket = to_node.inputs[index]
                node_tree.links.new(from_socket, to_socket)

    for node in imported_nodes_dic.values():
        node.select = True

def make_group_copy(node_tree, src_node_group):
    if 'SHADER' == node_tree.type:
        data_group = bpy.data.node_groups.new(src_node_group.name, 'ShaderNodeTree')
        node_group = node_tree.nodes.new('ShaderNodeGroup')
        node_group.node_tree = data_group
    elif 'GEOMETRY' == node_tree.type:
        data_group = bpy.data.node_groups.new(src_node_group.name, 'GeometryNodeTree')
        node_group = node_tree.nodes.new('GeometryNodeGroup')
        node_group.node_tree = data_group
    else:
        raise Exception("Error, no match for tree type!")

    node_group.node_tree.name = src_node_group.node_tree.name

    # create inputs and outputs
    for src_inp in src_node_group.inputs:
        node_group.inputs.new(src_inp.rna_type.identifier, src_inp.name)
    for src_opt in src_node_group.outputs:
        node_group.outputs.new(src_opt.rna_type.identifier, src_opt.name)

    return node_group

def make_group_from_node(node_tree, src_node):
    if 'SHADER' == node_tree.type:
        data_group = bpy.data.node_groups.new(src_node.name, 'ShaderNodeTree')
        node_group = node_tree.nodes.new('ShaderNodeGroup')
        node_group.node_tree = data_group
    elif 'GEOMETRY' == node_tree.type:
        data_group = bpy.data.node_groups.new(src_node.name, 'GeometryNodeTree')
        node_group = node_tree.nodes.new('GeometryNodeGroup')
        node_group.node_tree = data_group
    else:
        raise Exception("Error, no match for tree type!")

    # change socket type to current node tree type
    def re_type(type):
        if 'shader' in type.lower():
            return 'NodeSocketGeometry'
        if 'geom' in type.lower():
            return 'NodeSocketShader'
        return type

    # create inputs and outputs
    for src_inp in src_node.inputs:
        type = re_type(src_inp.rna_type.identifier)
        node_group.inputs.new(type, src_inp.name)
    for src_opt in src_node.outputs:
        type = re_type(src_opt.rna_type.identifier)
        node_group.outputs.new(type, src_opt.name)

    # set some custom properties
    node_group['bb_type'] = 'mix'
    node_group.use_custom_color = True
    node_group.color = (0.7919, 0.4828, 0.3737)
    node_group.label = src_node.label

    return node_group

# transfer props to new nodes
def transfer_props(pasted_node, src_node):
    # copy basic props
    for prop in src_node.bl_rna.properties[2:]:
        identifier = prop.identifier

        # copy standard properties
        if not prop.is_readonly and identifier != 'parent':
            attr = getattr(src_node, identifier)
            setattr(pasted_node, identifier, attr)

    # handle ColorRamp type VALTORGB node
    if src_node.type == 'VALTORGB':
        for prop in pasted_node.color_ramp.bl_rna.properties[2:]:
            identifier = prop.identifier
            if not prop.is_readonly and 'bl_' not in identifier and identifier != 'parent':
                attr = getattr(src_node.color_ramp, identifier)                        
                setattr(pasted_node.color_ramp, identifier, attr)
                        
        # set color stops (elements)
        while len(pasted_node.color_ramp.elements) < len(src_node.color_ramp.elements):
            pasted_node.color_ramp.elements.new(0)
        for i, e in enumerate(src_node.color_ramp.elements):
            pasted_node.color_ramp.elements[i].position = e.position
            pasted_node.color_ramp.elements[i].color = e.color

    # handle location for GROUP_INPUT/OUTPUT
    if src_node.type in ['GROUP_INPUT', 'GROUP_OUTPUT']:
        pasted_node.location = src_node.location

# transfer location
def transfer_location(pasted_node, src_node):
    if src_node.parent:
        pasted_node.location = src_node.location + src_node.parent.location
    else:
        pasted_node.location = src_node.location

# convert node types from .blend
def get_node_from_file(node_tree, append_node_name):
    # path to file
    asset_blend_path = __file__.replace("node_transfer_op.py", "node_groups.blend")
    with bpy.data.libraries.load(asset_blend_path, link=False) as (data_from, data_to):
        data_to.node_groups = [append_node_name]
    
    ngroup = bpy.data.node_groups[append_node_name]

    if 'SHADER' == node_tree.type:
        node_group = node_tree.nodes.new('ShaderNodeGroup')
        node_group.node_tree = ngroup
    elif 'GEOMETRY' == node_tree.type:
        node_group = node_tree.nodes.new('GeometryNodeGroup')
        node_group.node_tree = ngroup
    
    return node_group