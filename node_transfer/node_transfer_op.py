import bpy


class BB_NodeTree():
    def __init__(self):
        self.active_nodes = {}
        self.type = ""


class BOOSTER_OT_CopyNodes(bpy.types.Operator):
    """Copy nodes from the context editor"""
    bl_idname = "scene.booster_copy_nodes"
    bl_description = "Copy node selection."
    bl_label = "Copy Nodes"

    @classmethod
    def poll(self, context):
        if context.space_data.node_tree and context.space_data.node_tree.type in ('SHADER','GEOMETRY'):
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
            if area.type == "NODE_EDITOR":
                area.tag_redraw()

        return {"FINISHED"}

def set_socket_index(node_tree):
    if node_tree == None:
        return

    for node in node_tree.nodes:
        if node.type == "GROUP":
            set_socket_index(node.node_tree)

        for i, inp in enumerate(node.inputs):
            for lnk in inp.links:
                lnk.to_socket["index"] = i


class BOOSTER_OT_PasteNodes(bpy.types.Operator):
    """Paste nodes into the context editor"""
    bl_idname = "scene.booster_paste_nodes"
    bl_description = "Paste node selection."
    bl_label = "Paste Nodes"

    @classmethod
    def poll(self, context):
        if context.space_data.node_tree and context.space_data.node_tree.type in ('SHADER','GEOMETRY'):
            if hasattr(context.scene, 'booster_src_node_tree'):
                return True
        
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

        return {"FINISHED"}

def transfer_nodes(node_tree, src_node_tree, inside_group=False):
    # store transfered nodes using original node names as keys
    # this way node name changes don"t cause a problem
    imported_nodes_dic = {}

    for src_node in src_node_tree.active_nodes.values():
        # switch to material output node if not inside a group node
        if inside_group == False and node_tree.type == "SHADER" and src_node.type == "GROUP_OUTPUT":
            pasted_node = node_tree.nodes.new("ShaderNodeOutputMaterial")
        # handle Group node
        elif src_node.type == "GROUP":
            pasted_node = make_group_copy(node_tree, src_node)

            pasted_node["bb_type"] = "transfer"

            # transfer nodes in group
            sub_src_node_tree = BB_NodeTree()
            for n in src_node.node_tree.nodes:
                sub_src_node_tree.active_nodes[n.name] = n
                sub_src_node_tree.type = src_node_tree.type

            transfer_nodes(pasted_node.node_tree, sub_src_node_tree, True)
        # handle all other nodes
        else:
            node_type = src_node.type.title()
            # handle special cases for textures
            if "noise" in node_type.lower():
                node_type = [piece.title() for piece in node_type.split("_")]
                node_type = "".join(node_type)

            # add new copied node or generate node if id not available
            try:
                pasted_node = node_tree.nodes.new(src_node.bl_idname)
                transfer_props(pasted_node, src_node)
                pasted_node["bb_type"] = "transfer"
            except RuntimeError:
                # see if our blend file has a replacement node
                pasted_node = get_node_from_file(node_tree, src_node.bl_rna.identifier)
                if pasted_node == None:
                    print("BOOSTER: Cannot add node id:", src_node.bl_idname)
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

        if node.type in ["REROUTE", "FRAME"]:
            continue

        # skip nodes that have been replaced
        if node.get("bb_type") == "mix":
            continue

        src_node = src_node_tree.active_nodes[name]

        # transfer outputs
        if node.type == "VALUE":
            node.outputs[0].default_value = src_node.outputs[0].default_value
            continue

        # transfer inputs
        for i, inp in enumerate(src_node.inputs):
            if (node.inputs[i].bl_rna.identifier not in 
            ("NodeSocketVirtual", "NodeSocketShader", "NodeSocketGeometry")):
                node.inputs[i].default_value = inp.default_value

    # generate links in the node tree for each added node
    for name, node in imported_nodes_dic.items():
        if node.type == "FRAME":
            continue

        src_node = src_node_tree.active_nodes[name]

        # for each node output make new links
        for i, opt in enumerate(src_node.outputs):
            for lnk in opt.links:
                to_node = imported_nodes_dic.get(lnk.to_node.name)
                from_node = imported_nodes_dic.get(lnk.from_node.name)

                if to_node == None:
                    continue

                index = lnk.to_socket.get("index")
                to_socket = to_node.inputs[index]
                from_socket = from_node.outputs[i]
                node_tree.links.new(from_socket, to_socket)

    for node in imported_nodes_dic.values():
        node.select = True

def check_socket_type(socket_type, node_tree_type):
    if node_tree_type == "SHADER":
        if socket_type == 'NodeSocketVectorEuler':
            return 'NodeSocketVector'

        if socket_type not in ('NodeSocketVector', 'NodeSocketFloat', 'NodeSocketColor'):
            return 'NodeSocketShader'
    
    else:
        if socket_type == 'NodeSocketFloatFactor':
            return 'NodeSocketFloat'

        if socket_type not in ('NodeSocketString', 'NodeSocketBool', 'NodeSocketMaterial', 
            'NodeSocketVector', 'NodeSocketInt', 'NodeSocketMenu', 'NodeSocketCollection',
            'NodeSocketTexture', 'NodeSocketFloat', 'NodeSocketColor', 'NodeSocketObject',
            'NodeSocketRotation', 'NodeSocketMatrix', 'NodeSocketImage'):

            return 'NodeSocketGeometry'
    
    return socket_type

def make_group_copy(node_tree, src_node):
    if "SHADER" == node_tree.type:
        data_group = bpy.data.node_groups.new(src_node.name, "ShaderNodeTree")
        node_group = node_tree.nodes.new("ShaderNodeGroup")
    elif "GEOMETRY" == node_tree.type:
        data_group = bpy.data.node_groups.new(src_node.name, "GeometryNodeTree")
        node_group = node_tree.nodes.new("GeometryNodeGroup")
    else:
        raise Exception("Error, no match for tree type!")

    for src_inp in src_node.inputs:
        socket_type = check_socket_type(src_inp.bl_idname, node_tree.type)
        data_group.interface.new_socket(name=src_inp.name, in_out='INPUT', socket_type=socket_type)
    
    for src_opt in src_node.outputs:
        socket_type = check_socket_type(src_opt.bl_idname, node_tree.type)
        data_group.interface.new_socket(name=src_opt.name, in_out='OUTPUT', socket_type=socket_type)
        
    node_group.node_tree = data_group

    return node_group

def make_group_from_node(node_tree, src_node):
    # Determine the node tree type and create a new node group accordingly
    if node_tree.type == "SHADER":
        data_group = bpy.data.node_groups.new(src_node.name, "ShaderNodeTree")
        node_group = node_tree.nodes.new("ShaderNodeGroup")
        node_group.node_tree = data_group
    elif node_tree.type == "GEOMETRY":
        data_group = bpy.data.node_groups.new(src_node.name, "GeometryNodeTree")
        node_group = node_tree.nodes.new("GeometryNodeGroup")
        node_group.node_tree = data_group
    else:
        raise Exception("Error, no match for tree type!")

    # Create inputs and outputs in the node group's node tree
    for src_inp in src_node.inputs:
        socket_type = check_socket_type(src_inp.bl_idname, node_tree.type)
        data_group.interface.new_socket(name=src_inp.name, in_out='INPUT', socket_type=socket_type)
    
    for src_opt in src_node.outputs:
        socket_type = check_socket_type(src_opt.bl_idname, node_tree.type)
        data_group.interface.new_socket(name=src_opt.name, in_out='OUTPUT', socket_type=socket_type)

    # set some custom properties
    node_group["bb_type"] = "mix"
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
        if not prop.is_readonly and identifier != "parent":
            attr = getattr(src_node, identifier)
            setattr(pasted_node, identifier, attr)

    # handle RGB and Vector Curves
    if src_node.type == "CURVE_RGB" or src_node.type == "CURVE_FLOAT" or src_node.type == "CURVE_VEC":
        # set points
        curves = pasted_node.mapping.curves
        src_curves = src_node.mapping.curves
        for i in range(len(curves)):
            points = curves[i].points
            src_points = src_curves[i].points

            # handle first and last point
            last_src_point = len(src_points) - 1
            points[0].location = src_points[0].location.copy()
            points[0].handle_type = src_points[0].handle_type
            points[1].location = src_points[last_src_point].location.copy()
            points[1].handle_type = src_points[last_src_point].handle_type

            # handle the rest
            for src_p in src_points[1:-1]:
                p = points.new(src_p.location[0], src_p.location[1])
                p.handle_type = src_p.handle_type

    # handle ColorRamp type VALTORGB node
    if src_node.type == "VALTORGB":
        for prop in pasted_node.color_ramp.bl_rna.properties[2:]:
            identifier = prop.identifier
            if not prop.is_readonly and "bl_" not in identifier and identifier != "parent":
                attr = getattr(src_node.color_ramp, identifier)                        
                setattr(pasted_node.color_ramp, identifier, attr)
                        
        # set color stops (elements)
        while len(pasted_node.color_ramp.elements) < len(src_node.color_ramp.elements):
            pasted_node.color_ramp.elements.new(0)
        for i, e in enumerate(src_node.color_ramp.elements):
            pasted_node.color_ramp.elements[i].position = e.position
            pasted_node.color_ramp.elements[i].color = e.color

    # handle location for GROUP_INPUT/OUTPUT
    if src_node.type in ["GROUP_INPUT", "GROUP_OUTPUT"]:
        pasted_node.location = src_node.location

# transfer location
def transfer_location(pasted_node, src_node):
    def get_frame_deep_location(node):
        loc = node.location.copy()
        if node.parent:
            loc += get_frame_deep_location(node.parent)
        return loc

    pasted_node.location = get_frame_deep_location(src_node)

# convert node types from .blend
def get_node_from_file(node_tree, append_node_name):
    # path to file
    asset_blend_path = __file__.replace("node_transfer_op.py", "node_groups.blend")
    with bpy.data.libraries.load(asset_blend_path, link=False) as (data_from, data_to):
        data_to.node_groups = [append_node_name]
    
    ngroup = bpy.data.node_groups.get(append_node_name)
    if ngroup:
        if "SHADER" == node_tree.type:
            node_group = node_tree.nodes.new("ShaderNodeGroup")
            node_group.node_tree = ngroup
        elif "GEOMETRY" == node_tree.type:
            node_group = node_tree.nodes.new("GeometryNodeGroup")
            node_group.node_tree = ngroup
        
        return node_group
    else:
        return None