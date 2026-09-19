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
model = ifcopenshell.file()
ifcopenshell.api.root.create_entity(model, ifc_class="IfcProject", name="Hospital Floor Plan")

length_unit = ifcopenshell.api.unit.add_si_unit(model, unit_type="LENGTHUNIT")
ifcopenshell.api.unit.assign_unit(model, units=[length_unit])

model3d = ifcopenshell.api.context.add_context(model, context_type="Model")
plan = ifcopenshell.api.context.add_context(model, context_type="Plan")
body = ifcopenshell.api.context.add_context(
    model,
    context_type="Model",
    context_identifier="Body",
    target_view="MODEL_VIEW",
    parent=model3d,
)

project = model.by_type("IfcProject")[0]
site = ifcopenshell.api.root.create_entity(model, ifc_class="IfcSite", name="Main Site")
building = ifcopenshell.api.root.create_entity(
    model, ifc_class="IfcBuilding", name="Hospital Building"
)
storey = model.create_entity("IfcBuildingStorey", Name="Ground Floor", Elevation=0.0)

model.create_entity("IfcRelAggregates", RelatingObject=project, RelatedObjects=[site])
model.create_entity("IfcRelAggregates", RelatingObject=site, RelatedObjects=[building])
model.create_entity("IfcRelAggregates", RelatingObject=building, RelatedObjects=[storey])

# ------------------------------------------------------------
# Hospital spaces
#
# Important: rooms below are deliberately separated by small gaps.
# This prevents the complete four-wall loops made by create_room()
# from occupying the same line or passing through one another.
# A continuous storey slab fills the gaps later in the script.
# ------------------------------------------------------------

hospital_rooms = {}

# West wing: food service and staff spaces
hospital_rooms["DiningRoomNorth"] = create_room(
    7.6, 4.1, "Dining Room North", np.array([0.5, 17.2, 0.0])
)
hospital_rooms["DiningRoomSouth"] = create_room(
    7.6, 4.1, "Dining Room South", np.array([0.5, 12.3, 0.0])
)
hospital_rooms["ServingArea"] = create_room(
    7.6, 4.4, "Serving Area", np.array([0.5, 7.1, 0.0])
)
hospital_rooms["PhysicianDining"] = create_room(
    3.2, 2.4, "Physician Dining", np.array([6.0, 3.7, 0.0])
)
hospital_rooms["WestElevatorLobby"] = create_room(
    2.0, 2.0, "West Elevator Lobby", np.array([3.5, 0.6, 0.0])
)

# North public wing
hospital_rooms["GiftShop"] = create_room(
    2.8, 2.3, "Gift Shop", np.array([10.0, 19.0, 0.0])
)
hospital_rooms["MainLobby"] = create_room(
    7.0, 3.0, "Main Hospital Lobby", np.array([14.0, 18.6, 0.0])
)
hospital_rooms["Chapel"] = create_room(
    3.0, 2.8, "Chapel", np.array([24.3, 18.8, 0.0])
)
hospital_rooms["NorthWaitingArea"] = create_room(
    6.3, 3.6, "North Waiting Area", np.array([29.0, 17.5, 0.0])
)

# Registration and separated circulation space
hospital_rooms["MainPatientRegistration"] = create_room(
    6.5, 2.8, "Main Patient Registration", np.array([18.6, 13.1, 0.0])
)
hospital_rooms["ERRegistration"] = create_room(
    3.4, 2.7, "ER Registration", np.array([29.0, 13.4, 0.0])
)
hospital_rooms["ERWaitingRoom"] = create_room(
    3.8, 3.1, "ER Waiting Room", np.array([34.0, 13.0, 0.0])
)
hospital_rooms["CentralCorridor"] = create_room(
    20.2, 1.3, "Central Corridor", np.array([11.2, 10.9, 0.0])
)
hospital_rooms["ERCorridor"] = create_room(
    1.1, 13.0, "Emergency Department Corridor", np.array([32.2, 2.6, 0.0])
)

# Diagnostic imaging wing
hospital_rooms["Ultrasound"] = create_room(
    5.1, 2.6, "Ultrasound", np.array([12.1, 7.2, 0.0])
)
hospital_rooms["MRI"] = create_room(
    6.4, 3.1, "MRI", np.array([10.4, 1.5, 0.0])
)
hospital_rooms["NuclearMedicine"] = create_room(
    6.5, 3.5, "Nuclear Medicine", np.array([18.2, 4.2, 0.0])
)
hospital_rooms["EKG"] = create_room(
    2.3, 2.3, "EKG", np.array([25.0, 8.0, 0.0])
)
hospital_rooms["XRay"] = create_room(
    3.1, 2.6, "X-Ray", np.array([28.6, 8.0, 0.0])
)
hospital_rooms["CentralElevatorLobby"] = create_room(
    1.9, 1.9, "Central Elevator Lobby", np.array([22.2, 10.1, 0.0])
)

# Emergency department
hospital_rooms["ERFastTrack"] = create_room(
    3.6, 4.5, "ER Fast Track", np.array([34.3, 8.0, 0.0])
)
hospital_rooms["ERTreatmentArea"] = create_room(
    3.6, 4.0, "ER Treatment Area", np.array([34.3, 2.6, 0.0])
)

# Numbered ER bays: small separated rooms to avoid wall overlap.
for bay_number, bay_y in zip(range(10, 16), [7.0, 5.8, 4.6, 3.4, 2.2, 1.0]):
    bay_name = f"ER Bay {bay_number}"
    hospital_rooms[f"ERBay{bay_number}"] = create_room(
        1.1, 0.85, bay_name, np.array([39.0, bay_y, 0.0])
    )

# ------------------------------------------------------------
# Continuous storey slab
#
# This fills all gaps between rooms and corridors. It is contained
# directly in the IfcBuildingStorey, not inside an individual room.
# The original create_slab() helper is used unchanged.
# ------------------------------------------------------------

hospital_continuous_slab = create_slab(
    length=41.2,
    width=21.5,
    name="Hospital Continuous Ground Floor Slab",
    origin=np.array([20.6, 10.75, -0.2]),
    ifcspace=storey,
)

# ------------------------------------------------------------
# Exterior envelope
#
# The plan has a stepped boundary. These wall segments approximate
# that outline and sit outside the room walls. They are deliberately
# segmented rather than represented by one large rectangle.
# ------------------------------------------------------------

exterior_walls = {}

# South edge and south-west / south-east returns
exterior_walls["SouthWest"] = create_wall(
    10.0, "Exterior Wall South West", np.array([0.0, -0.2, 0.0]), False, storey
)
exterior_walls["SouthCentre"] = create_wall(
    19.0, "Exterior Wall South Centre", np.array([10.8, -0.2, 0.0]), False, storey
)
exterior_walls["SouthEast"] = create_wall(
    10.5, "Exterior Wall South East", np.array([30.5, -0.2, 0.0]), False, storey
)

# North edge, separated to reflect the entrance/recessed frontage
exterior_walls["NorthWest"] = create_wall(
    10.0, "Exterior Wall North West", np.array([0.0, 21.7, 0.0]), False, storey
)
exterior_walls["NorthCentre"] = create_wall(
    13.0, "Exterior Wall North Centre", np.array([13.0, 21.7, 0.0]), False, storey
)
exterior_walls["NorthEast"] = create_wall(
    14.2, "Exterior Wall North East", np.array([26.8, 21.7, 0.0]), False, storey
)

# West facade with a small step to match the food-service projection
exterior_walls["WestSouth"] = create_wall(
    7.5, "Exterior Wall West South", np.array([-0.2, 0.0, 0.0]), True, storey
)
exterior_walls["WestMid"] = create_wall(
    9.0, "Exterior Wall West Middle", np.array([-0.2, 8.0, 0.0]), True, storey
)
exterior_walls["WestNorth"] = create_wall(
    5.0, "Exterior Wall West North", np.array([-0.2, 17.0, 0.0]), True, storey
)

# East facade, including the ER-side projection
exterior_walls["EastSouth"] = create_wall(
    9.0, "Exterior Wall East South", np.array([41.2, 0.0, 0.0]), True, storey
)
exterior_walls["EastER"] = create_wall(
    8.0, "Exterior Wall East Emergency", np.array([41.2, 9.5, 0.0]), True, storey
)
exterior_walls["EastNorth"] = create_wall(
    4.2, "Exterior Wall East North", np.array([41.2, 17.5, 0.0]), True, storey
)

# Short return walls make the stepped/recessed portions visible.
exterior_walls["WestFoodServiceReturn"] = create_wall(
    1.7, "Exterior Wall West Food Service Return", np.array([-0.2, 8.0, 0.0]), False, storey
)
exterior_walls["EastERReturn"] = create_wall(
    1.8, "Exterior Wall East ER Return", np.array([39.4, 9.5, 0.0]), False, storey
)
exterior_walls["NorthEntranceReturnWest"] = create_wall(
    1.0, "Exterior Wall Main Entrance Return West", np.array([13.0, 20.7, 0.0]), True, storey
)
exterior_walls["NorthEntranceReturnEast"] = create_wall(
    1.0, "Exterior Wall Main Entrance Return East", np.array([26.0, 20.7, 0.0]), True, storey
)

# ------------------------------------------------------------
# Output
# ------------------------------------------------------------

model.write("hospital_floor_plan_revised.ifc")
print("Hospital IFC model written to hospital_floor_plan_revised.ifc")