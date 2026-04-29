
import numpy as np
import ifcopenshell
import profile

def create_model():

    # the modules rely on "model" being defined in the global scope
    model = ifcopenshell.file()

    # create the root entity (IfcProject) and set it as the root of the model
    ifcopenshell.api.root.create_entity(model, ifc_class="IfcProject")

    # set coordinates to be in meters
    length = ifcopenshell.api.unit.add_si_unit(model, unit_type="LENGTHUNIT")
    ifcopenshell.api.unit.assign_unit(model, units=[length])

    # create contexts for 3D model, plan view and body
    model3d = ifcopenshell.api.context.add_context(model, context_type="Model")
    plan = ifcopenshell.api.context.add_context(model, context_type="Plan")
    body = ifcopenshell.api.context.add_context(model, 
        context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=model3d)

    # add some contexts for axes and annotations
    ifcopenshell.api.context.add_context(model,
        context_type="Model", context_identifier="Axis", target_view="GRAPH_VIEW", parent=model3d)
    ifcopenshell.api.context.add_context(model,
        context_type="Plan", context_identifier="Axis", target_view="GRAPH_VIEW", parent=plan)
    ifcopenshell.api.context.add_context(model,
        context_type="Model", context_identifier="Box", target_view="MODEL_VIEW", parent=model3d)
    ifcopenshell.api.context.add_context(model,
        context_type="Plan", context_identifier="Annotation", target_view="PLAN_VIEW", parent=plan)


    # create the project structure components for use in IfcRelAggregates
    project = model.by_type("IfcProject")[0]
    # site = ifcopenshell.api.root.create_entity(model, ifc_class="IfcSite", name="Main Site")
    # building = ifcopenshell.api.root.create_entity(model, ifc_class="IfcBuilding", name="Building")
    site = ifcopenshell.api.root.create_entity(model, ifc_class="IfcSite", name="Main Site")
    building = ifcopenshell.api.root.create_entity(model, ifc_class="IfcBuilding", name="Building")
    storey = model.create_entity("IfcBuildingStorey", Name="Ground", Elevation=0.0)

    # IfcRelAggregates is used to define the hierarchical structure of the building model.
    model.create_entity("IfcRelAggregates", RelatingObject=project, RelatedObjects=[site])
    model.create_entity("IfcRelAggregates", RelatingObject=site, RelatedObjects=[building])
    model.create_entity("IfcRelAggregates", RelatingObject=building, RelatedObjects=[storey])

    return model

def add_space(length, width, name, origin, height = 3.0):
    
    # create the specific room ifcspace and relate it to the storey in the model hierarchy
    ifcspace = ifcopenshell.api.root.create_entity(model, ifc_class="IfcSpace", name=name)
    model.create_entity("IfcRelAggregates", RelatingObject=storey, RelatedObjects=[ifcspace])

    # create the actual space entity with geometry and relate it to the ifcspace in the model hierarchy
    room_space = ifcopenshell.api.root.create_entity(model, ifc_class="IfcSpace", name=name)

    matrix = np.eye(4)
    matrix[:,3][0:3] = origin
    ifcopenshell.api.geometry.edit_object_placement(model, product=room_space, matrix=matrix, is_si=False)

    profile = model.create_entity("IfcRectangleProfileDef",
        ProfileName=f"{name} footprint", ProfileType="AREA", 
        XDim=length, YDim=width)
    
    space_rep = ifcopenshell.api.geometry.add_profile_representation(
        model, context=body, profile=profile, depth=height)
    
    model.create_entity("IfcRelContainedInSpatialStructure", RelatingStructure=ifcspace, RelatedElements=[room_space])

    return ifcspace, room_space


# define a function to add ifcwall to the model
def add_wall(length, name: str, origin, rotate, ifcspace):
    wall = ifcopenshell.api.root.create_entity(model, ifc_class="IfcWall", name=name)
    
    wall_rep = ifcopenshell.api.geometry.add_wall_representation(model,
        context=body, length=length, height=3.0, thickness=0.2)
    
    matrix = np.eye(4)
    if rotate:
        matrix = ifcopenshell.util.placement.rotation(90, "Z") @ matrix
    matrix[:,3][0:3] = origin
    
    ifcopenshell.api.geometry.edit_object_placement(model, product=wall, matrix=matrix, is_si=False)
    ifcopenshell.api.geometry.assign_representation(model, product=wall, representation=wall_rep)

    # this part is important because it relates the wall back to the hierarchy of the ifc model defined before
    ifcopenshell.api.spatial.assign_container(model, relating_structure=ifcspace, products=[wall])

    return wall

def add_slab(length, width, name, origin, ifcspace):
    slab = ifcopenshell.api.root.create_entity(model, ifc_class="IfcSlab", name=name)

    # Create a rectangular profile for the slab with your desired dimensions
    profile = model.create_entity("IfcRectangleProfileDef", ProfileName="slab", ProfileType="AREA",
        XDim=length, YDim=width)

    slab_rep = ifcopenshell.api.geometry.add_profile_representation(model, context=body, profile=profile, depth=0.2)

    matrix = np.eye(4)
    matrix[:,3][0:3] = origin
    ifcopenshell.api.geometry.edit_object_placement(model, product=slab, matrix=matrix, is_si=True)
    ifcopenshell.api.geometry.assign_representation(model, product=slab, representation=slab_rep)
    ifcopenshell.api.spatial.assign_container(model, relating_structure=ifcspace, products=[slab])
    
    return slab


# define a function to add a room to the model, which is just an ifcspace with physical geometry assigned
def add_room(length, width, name, origin):
    
    room_dict = {}

    [ifcspace, space] = add_space(length=length, width=width, name=name, origin=origin+np.array([length/2, width/2, 0]))

    room_dict[name+"wallN"] = add_wall(length=length, name=name+"wallN", origin=origin+np.array([0, width, 0]), rotate=False, ifcspace=ifcspace)
    room_dict[name+"wallS"] = add_wall(length=length, name=name+"wallS", origin=origin+np.array([0,-0.2,0]), rotate=False, ifcspace=ifcspace)

    room_dict[name+"wallE"] = add_wall(length=width+0.4, name=name+"wallE", origin=origin+np.array([length+0.2, -0.2, 0]), rotate=True, ifcspace=ifcspace)
    room_dict[name+"wallW"] = add_wall(length=width+0.4, name=name+"wallW", origin=origin+np.array([0, -0.2, 0]), rotate=True, ifcspace=ifcspace)

    room_dict[name+"slab"] = add_slab(length=length+0.4, width=width+0.4, name=name+"slab", origin=origin+np.array([length/2, width/2, -0.2]), ifcspace=ifcspace)   
    
    return [space, room_dict]