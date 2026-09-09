import numpy as np
import ifcopenshell

# for some reason ifcopenshell.api is not imported when importing ifcopenshell, so we need to import it explicitly
import ifcopenshell.api.root
import ifcopenshell.api.unit
import ifcopenshell.api.context
import ifcopenshell.api.project
import ifcopenshell.api.geometry

import profile

# -----------------------------------
### define functions

## functions to generate the geometry

def create_space(length, width, name, origin, height = 3.0):
    
    # create the specific room ifcspace and relate it to the storey in the model hierarchy
    ifcspace = ifcopenshell.api.root.create_entity(model, ifc_class="IfcSpace", name=name)
    model.create_entity("IfcRelAggregates", RelatingObject=storey, RelatedObjects=[ifcspace])

    # create the actual space entity with geometry and relate it to the ifcspace in the model hierarchy
    room_space = ifcopenshell.api.root.create_entity(model, ifc_class="IfcSpace", name=name)
    # model.create_entity("IfcRelAggregates", RelatingObject=storey, RelatedObjects=[space])

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
def create_wall(length, name: str, origin, rotate, ifcspace):
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

def create_slab(length, width, name, origin, ifcspace):
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
def create_room(length, width, name, origin):
    
    room_dict = {}

    [ifcspace, space] = create_space(length=length, width=width, name=name, origin=origin+np.array([length/2, width/2, 0]))

    room_dict[name+"wallN"] = create_wall(length=length, name=name+"wallN", origin=origin+np.array([0, width, 0]), rotate=False, ifcspace=ifcspace)
    room_dict[name+"wallS"] = create_wall(length=length, name=name+"wallS", origin=origin+np.array([0,-0.2,0]), rotate=False, ifcspace=ifcspace)

    room_dict[name+"wallE"] = create_wall(length=width+0.4, name=name+"wallE", origin=origin+np.array([length+0.2, -0.2, 0]), rotate=True, ifcspace=ifcspace)
    room_dict[name+"wallW"] = create_wall(length=width+0.4, name=name+"wallW", origin=origin+np.array([0, -0.2, 0]), rotate=True, ifcspace=ifcspace)

    room_dict[name+"slab"] = create_slab(length=length+0.4, width=width+0.4, name=name+"slab", origin=origin+np.array([length/2, width/2, -0.2]), ifcspace=ifcspace)   
    
    return [space, room_dict]


# Define a function to add space boundaries to the model. 
# This function creates an IfcRelSpaceBoundary entity, relates it to the space and the building element, 
# and sets the physical and internal/external attributes.

def create_rel(space, element, physical="VIRTUAL", internal_external="INTERNAL", name=None):
    rel = ifcopenshell.api.root.create_entity(
        model,
        ifc_class="IfcRelSpaceBoundary2ndLevel",
        name=name
    )
    ifcopenshell.api.boundary.edit_attributes(
        model,
        entity=rel,
        relating_space=space,
        related_building_element=element,
    )
    rel.PhysicalOrVirtualBoundary = physical
    rel.InternalOrExternalBoundary = internal_external
    return rel


# adds openings, specifically for doors
# for now, this requires knowledge of both the walls of both spaces, including names. Can be tedious

# this currently creates two openings if there are two walls, but they are both related to the same opening element for simplicity. 
# This is because the opening element is what relates the two spaces together, and the geometry is just for visualisation purposes.
# this does not mean that the extra opening is a "leftover" element within the IFC model. It exists purely as a physical geometrical visualisation. It is not ever represented as relationship to an IfcSpace.
# openings are essentially viewed as subtractions to the wall.
# as a matter of fact, you cannot simply (or at least conventionally) define a relationship between an opening and any other object directly. However they can be defined as the link between two IfcSpace entities.
def create_opening(width, height, name, origin, ifcspace1, wall1, ifcspace2=None, wall2=None):
    opening = ifcopenshell.api.root.create_entity(model, ifc_class="IfcOpeningElement", name=name)
    opening_rep = ifcopenshell.api.geometry.add_wall_representation(model,
        context=body, length=width, height=height, thickness=0.4)
    ifcopenshell.api.geometry.assign_representation(model, product=opening, representation=opening_rep)

    matrix = np.eye(4)
    if wall1.Name[-1] == "W" or wall1.Name[-1] == "E":
        matrix = ifcopenshell.util.placement.rotation(90, "Z") @ matrix
    matrix[:,3][0:3] = origin

    ifcopenshell.api.geometry.edit_object_placement(model, product=opening, matrix=matrix, is_si=True)

    # issue. I suspect that this will need to select both walls that the opening intersects with
    # i think it's fine, because technically i just need to know which space the opening connects to.
    # plus i am manually placing the openings. it's more for geometry and visuals
    ifcopenshell.api.feature.add_feature(model, feature=opening, element=wall1)
    ifcopenshell.api.spatial.assign_container(model, relating_structure=ifcspace1, products=[opening])


    if (wall2 is not None):
        opening2 = ifcopenshell.api.root.create_entity(model, ifc_class="IfcOpeningElement", name=name)
        opening2_rep = ifcopenshell.api.geometry.add_wall_representation(model,
            context=body, length=width, height=height, thickness=0.4)
        ifcopenshell.api.geometry.assign_representation(model, product=opening2, representation=opening2_rep)

        ifcopenshell.api.geometry.edit_object_placement(model, product=opening2, matrix=matrix, is_si=True)

        ifcopenshell.api.feature.add_feature(model, feature=opening2, element=wall2)
        ifcopenshell.api.spatial.assign_container(model, relating_structure=ifcspace2, products=[opening2])
        # b2=create_rel(ifcspace2, opening2, name=name+"_Boundary")
        
        # create two way relationship entities between two rooms
        b1=create_rel(ifcspace1, opening, name=name+"_Boundary")
        b2=create_rel(ifcspace2, opening, name=name+"_Boundary")

        # the below is the same as create_space_boundary but with an added element
        ifcopenshell.api.boundary.edit_attributes(
            model,
            entity=b1,
            relating_space=ifcspace1,
            related_building_element=opening,
            corresponding_boundary=b2
        )

        ifcopenshell.api.boundary.edit_attributes(
            model,
            entity=b2,
            relating_space=ifcspace2,
            related_building_element=opening, # this is intentional, so b2 can be related to b1 through the same opening. openign2 is just for geometry visualisation
            corresponding_boundary=b1
        )
    return opening

### define functions end
# -----------------------------------


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

# ---------------------------------


