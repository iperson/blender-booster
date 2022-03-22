from ast import NodeTransformer
import bpy
import re


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
        # node_name : outputs[] > links [] > (node_name :, socket_name :)
        bpy.types.Scene.booster_src_node_dic = {}
        bpy.types.Scene.booster_src_node_tree_data = {}

        # for each link in each output in each node
        # store connected node name and socket
        for node in context.selected_nodes:
            outputs = []
            for out in node.outputs:
                links = []
                for lnk in out.links:
                    links.append(
                        {'node_name' : lnk.to_node.name,
                        'socket_name' : lnk.to_socket.identifier}
                        )
                outputs.append(links)

            context.scene.booster_src_node_tree_data[node.name] = outputs
            context.scene.booster_src_node_dic[node.name] = node

        # update Paste buttons
        for area in bpy.context.window.screen.areas:
            if area.type == 'NODE_EDITOR':
                area.tag_redraw()

        return {'FINISHED'}


class BOOSTER_OT_PasteNodes(bpy.types.Operator):
    """Paste nodes into the context editor"""
    bl_idname = "scene.booster_paste_nodes"
    bl_label = "Paste Nodes"

    @classmethod
    def poll(self, context):
        try:
            context.scene.booster_src_node_dic
            return True
        except:
            return False

    def execute(self, context):
        # local node group
        node_tree = context.space_data.node_tree
        src_node_tree_data = context.scene.booster_src_node_tree_data
        src_node_dic = context.scene.booster_src_node_dic

        # deselect all nodes
        for node in node_tree.nodes:
            node.select = False

        imported_nodes_dic = {}
        # imported_node_names = []

        # paste nodes into node tree
        for node in src_node_dic.values():
            node_type = node.type.title()

            # handle special cases for textures
            if 'noise' in node_type.lower():
                node_type = [piece.title() for piece in node_type.split('_')]
                node_type = ''.join(node_type)

            # add new copied node or generate node if id not available
            try:
                pasted_node = node_tree.nodes.new(node.bl_idname)
            except RuntimeError:
                print("BOOSTER: Cannot add node id:", node.bl_idname)
                pasted_node = node_tree.nodes.new('ShaderNodeMixRGB')
                pasted_node.use_custom_color = True
                pasted_node.color = (0.5,0,0)
                pasted_node.label = "{} _BB_replaced".format(node.name)
                if node.parent:
                    pasted_node.location = node.location + node.parent.location
                else:
                    pasted_node.location = node.location
                imported_nodes_dic[node.name] = pasted_node
                continue

            imported_nodes_dic[node.name] = pasted_node

            # copy props
            for prop in node.bl_rna.properties[2:]:
                identifier = prop.identifier
                # handle location for nodes with layout
                if node.parent and identifier == 'location':
                    pasted_node.location = node.location + node.parent.location
                # copy standard properties
                elif not prop.is_readonly and 'bl_' not in identifier and identifier != 'parent':
                    attr = getattr(node, identifier)                        
                    try:
                        vars(attr)
                    except TypeError:
                        if type(attr) != 'PointerProperty':
                            setattr(pasted_node, identifier, attr)

            # handle ColorRamp type VALTORGB node
            if node.type == 'VALTORGB':
                for prop in pasted_node.color_ramp.bl_rna.properties[2:]:
                    identifier = prop.identifier
                    if not prop.is_readonly and 'bl_' not in identifier and identifier != 'parent':
                        attr = getattr(node.color_ramp, identifier)                        
                        try:
                            vars(attr)
                        except TypeError:
                            if type(attr) != 'PointerProperty':
                                setattr(pasted_node.color_ramp, identifier, attr)
                # set color stops (elements)
                while len(pasted_node.color_ramp.elements) < len(node.color_ramp.elements):
                    pasted_node.color_ramp.elements.new(0)
                for i, e in enumerate(node.color_ramp.elements):
                    pasted_node.color_ramp.elements[i].position = e.position
                    pasted_node.color_ramp.elements[i].color = e.color

        # add nodes to frames
        for src_name, src_node in src_node_dic.items():
            # add to frame
            if src_node.parent != None:
                frame_node = imported_nodes_dic.get(src_node.parent.name)
                node = imported_nodes_dic.get(src_name)

                if frame_node and node:
                    node.parent = frame_node                

        # transfer socket values
        for name, node in imported_nodes_dic.items():
            if node.type in ['REROUTE', 'FRAME']:
                continue

            if '_BB_replaced' in node.label:
                continue

            if name != src_node_dic[name].name:
                raise NameError

            src_inputs = src_node_dic[name].inputs
            for index, inp in enumerate(src_inputs):
                print()
                print(name)
                print(node.name)
                print(src_node_dic[name].name)
                print(inp.default_value)
                print(inp)
                node.inputs[index].default_value = inp.default_value

        # generate links in the node tree for each added node
        for node_name, node in imported_nodes_dic.items():
            if node.type == 'FRAME':
                continue

            src_node = src_node_dic[node_name]

            # for each node output make new links
            for o in src_node.outputs:
                for lnk in o.links:
                    try:
                        to_socket_name = lnk.to_socket.identifier
                        to_node_name = lnk.to_node.name
                        # get index from the end of the scoket name SocketName.001
                        socket_index = int('0' + ''.join(re.findall(r'\d+', to_socket_name)))
                        to_socket = imported_nodes_dic[to_node_name].inputs[socket_index]

                        # handle substitution nodes
                        if node.type != src_node:
                            from_socket = o[0]
                        else:
                            from_socket = imported_nodes_dic[node_name].outputs[o.identifier]
                            
                        node_tree.links.new(from_socket, to_socket)
                    except KeyError:
                        print("BOOSTER: Linking error from {} to {}.".format(node_name, to_node_name))
                            
        # remove temp globals
        del bpy.types.Scene.booster_src_node_dic
        del bpy.types.Scene.booster_src_node_tree_data

        return {'FINISHED'}
