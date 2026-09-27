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
import ifcopenshell.api.feature
import ifcopenshell.api.spatial
import ifcopenshell.api.boundary
import ifcopenshell.util.placement

# Rectangles are (x_left, y_bottom, length_x, width_y).
# Shared boundaries are intentional; identical room/corridor wall faces are
# opened in pairs. Dedicated top and south corridor bands are non-overlapping.
ROOMS = {
    "Staff and meeting":       (0.0, 20.0, 3.5, 4.0),
    "Operating room 1":        (3.5, 20.0, 7.5, 4.0),
    "Theatre support":         (0.0, 12.0, 3.5, 6.0),
    "Operating room 2":        (3.5, 12.0, 7.5, 6.0),
    "Sterile set-up":          (0.0, 0.0, 3.5, 6.0),
    "Operating room 3":        (3.5, 0.0, 7.5, 6.0),
    "Operating room 4":        (12.0, 20.0, 4.0, 4.0),
    "Scope processing":        (16.0, 20.0, 4.5, 4.0),
    "Hybrid theatre":          (12.0, 12.0, 8.5, 6.0),
    "Sterile stock":           (12.0, 0.0, 5.0, 6.0),
    "Cath lab":                (17.0, 0.0, 3.5, 6.0),
    "Recovery bays 1-3":      (22.0, 20.0, 4.0, 4.0),
    "Recovery bays 4-8":      (26.0, 20.0, 5.5, 4.0),
    "Recovery bays 9-12":     (33.0, 20.0, 4.0, 4.0),
    "Recovery bays 13-16":    (37.0, 20.0, 4.0, 4.0),
    "Patient bay hold A":      (22.0, 12.0, 4.0, 6.0),
    "Recovery station":        (26.0, 12.0, 3.0, 6.0),
    "Recovery utility":        (29.0, 12.0, 2.5, 6.0),
    "Patient bay hold B":      (33.0, 12.0, 4.0, 6.0),
    "Recovery beds":          (37.0, 12.0, 4.0, 6.0),
    "Lab support":            (22.0, 0.0, 4.0, 6.0),
    "Patient lobby":          (26.0, 0.0, 3.0, 6.0),
    "Lifts and stairs":       (29.0, 0.0, 2.5, 6.0),
    "Waiting and reception":  (33.0, 0.0, 4.0, 6.0),
    "Consult and offices":    (37.0, 3.0, 4.0, 3.0),
    "Staff amenities":       (37.0, 0.0, 4.0, 3.0),
}

# Corridor graph: all these rectangular circulation spaces are connected.
CORRIDORS = {
    "Recovery circulation": (12.0, 24.0, 29.0, 1.0),
    "Theatre spine":        (11.0, 0.0, 1.0, 25.0),
    "Clinical spine":       (20.5, 0.0, 1.5, 25.0),
    "Public spine":         (31.5, 0.0, 1.5, 25.0),
    "North cross corridor": (0.0, 18.0, 41.0, 2.0),
    "South cross corridor": (0.0, 6.0, 41.0, 2.0),
}

hospital_rooms = {}
for room_name, (x, y, dx, dy) in ROOMS.items():
    hospital_rooms[room_name] = create_room(dx, dy, room_name,
                                             np.array([x, y, 0.0]))

hospital_corridors = {}
for corridor_name, (x, y, dx, dy) in CORRIDORS.items():
    hospital_corridors[corridor_name] = create_room(dx, dy, corridor_name,
                                                   np.array([x, y, 0.0]))

ALL = {**hospital_rooms, **hospital_corridors}
BOXES = {**ROOMS, **CORRIDORS}

# A full, single floor plate fills areas between rooms. Existing room slabs
# remain, so slabs overlap locally; exclude/hide them if necessary in viewer.
hospital_floor_plate = create_slab(
    length=41.0, width=25.0, name="Continuous Level 1 floor plate",
    origin=np.array([20.5, 12.5, -0.4]), ifcspace=storey
)

# Helpers to resolve wall dictionary keys and derive a shared-wall opening.
SIDES = {"N": "S", "S": "N", "E": "W", "W": "E"}

def wall_of(name, side):
    return ALL[name][1][name + "wall" + side]

def add_connection(a, side_a, b, centre, width=1.2):
    """Create paired wall cuts at an actual shared room/corridor boundary."""
    side_b = SIDES[side_a]
    ax, ay, al, aw = BOXES[a]
    bx, by, bl, bw = BOXES[b]
    eps = 1e-7
    if side_a in ("N", "S"):
        y = ay + aw if side_a == "N" else ay
        other_y = by if side_a == "N" else by + bw
        lo, hi = max(ax, bx), min(ax + al, bx + bl)
        if abs(y - other_y) > eps or not lo + 0.3 <= centre - width / 2 or centre + width / 2 > hi - 0.3:
            raise ValueError(f"Invalid shared horizontal boundary: {a} -> {b}")
        origin = np.array([centre - width / 2, y - 0.1, 0.0])
    else:
        x = ax + al if side_a == "E" else ax
        other_x = bx if side_a == "E" else bx + bl
        lo, hi = max(ay, by), min(ay + aw, by + bw)
        if abs(x - other_x) > eps or not lo + 0.3 <= centre - width / 2 or centre + width / 2 > hi - 0.3:
            raise ValueError(f"Invalid shared vertical boundary: {a} -> {b}")
        origin = np.array([x - 0.1, centre - width / 2, 0.0])
    label = f"Opening: {a} to {b}"
    create_opening(width=width, height=2.1, name=label, origin=origin,
                   ifcspace1=ALL[a][0], wall1=wall_of(a, side_a),
                   ifcspace2=ALL[b][0], wall2=wall_of(b, side_b))

# Every non-circulation room gets one opening onto a directly adjacent
# circulation rectangle. Centre coordinates are along the common wall.
CONNECTIONS = [
    ("Staff and meeting", "S", "North cross corridor", 1.8, 1.1),
    ("Operating room 1", "S", "North cross corridor", 7.0, 1.4),
    ("Theatre support", "N", "North cross corridor", 1.8, 1.1),
    ("Operating room 2", "E", "Theatre spine", 15.0, 1.4),
    ("Sterile set-up", "N", "South cross corridor", 1.8, 1.1),
    ("Operating room 3", "E", "Theatre spine", 3.0, 1.4),
    ("Operating room 4", "S", "North cross corridor", 14.0, 1.4),
    ("Scope processing", "S", "North cross corridor", 18.0, 1.1),
    ("Hybrid theatre", "N", "North cross corridor", 16.0, 1.5),
    ("Sterile stock", "N", "South cross corridor", 14.5, 1.2),
    ("Cath lab", "N", "South cross corridor", 18.5, 1.3),
    ("Recovery bays 1-3", "N", "Recovery circulation", 24.0, 1.3),
    ("Recovery bays 4-8", "N", "Recovery circulation", 28.5, 1.3),
    ("Recovery bays 9-12", "N", "Recovery circulation", 35.0, 1.3),
    ("Recovery bays 13-16", "N", "Recovery circulation", 39.0, 1.3),
    ("Patient bay hold A", "N", "North cross corridor", 24.0, 1.3),
    ("Recovery station", "N", "North cross corridor", 27.5, 1.1),
    ("Recovery utility", "N", "North cross corridor", 30.0, 1.1),
    ("Patient bay hold B", "N", "North cross corridor", 35.0, 1.3),
    ("Recovery beds", "N", "North cross corridor", 39.0, 1.3),
    ("Lab support", "N", "South cross corridor", 24.0, 1.2),
    ("Patient lobby", "N", "South cross corridor", 27.5, 1.3),
    ("Lifts and stairs", "N", "South cross corridor", 30.2, 1.2),
    ("Waiting and reception", "N", "South cross corridor", 35.0, 1.3),
    ("Consult and offices", "N", "South cross corridor", 39.0, 1.1),
    ("Staff amenities", "N", "Consult and offices", 39.0, 1.1),
    # Main corridors cross the three north-south spines.
    ("North cross corridor", "S", "Theatre spine", 11.5, 0.8),
]

# The last entry above is deliberately not used: north corridor and spine
# intersect at right angles, not along a full shared edge. The same applies
# to all six corridor crossings. Opening geometry must be cut in each crossing
# wall; intersection connectivity is explicit in CORRIDOR_CROSSINGS below.
CONNECTIONS.pop()

for a, side, b, centre, opening_width in CONNECTIONS:
    add_connection(a, side, b, centre, opening_width)

# North recovery circulation adjoins all three vertical spines at its south
# side. It joins the cross corridor through those spines. No opening is cut at
# those spine contacts here because they are T/intersection wall geometries.
CORRIDOR_CROSSINGS = [
    ("Theatre spine", "North cross corridor", 11.5, 19.0),
    ("Clinical spine", "North cross corridor", 21.25, 19.0),
    ("Public spine", "North cross corridor", 32.25, 19.0),
    ("Theatre spine", "South cross corridor", 11.5, 7.0),
    ("Clinical spine", "South cross corridor", 21.25, 7.0),
    ("Public spine", "South cross corridor", 32.25, 7.0),
    ("Theatre spine", "Recovery circulation", 12.0, 24.5),
    ("Clinical spine", "Recovery circulation", 21.25, 24.5),
    ("Public spine", "Recovery circulation", 32.25, 24.5),
]

# Exterior walls use your create_wall; gaps at entrance/stair exits are made
# by segmenting the exterior rather than calling create_opening(None,...).
exterior_walls = [
    create_wall(4.0, "Exterior south west", np.array([0.0, -0.4, 0.0]), False, storey),
    create_wall(23.5, "Exterior south centre", np.array([5.5, -0.4, 0.0]), False, storey),
    create_wall(10.5, "Exterior south east", np.array([30.5, -0.4, 0.0]), False, storey),
    create_wall(3.0, "Exterior north west", np.array([0.0, 25.1, 0.0]), False, storey),
    create_wall(27.0, "Exterior north centre", np.array([4.5, 25.1, 0.0]), False, storey),
    create_wall(8.0, "Exterior north east", np.array([33.0, 25.1, 0.0]), False, storey),
    create_wall(11.0, "Exterior west lower", np.array([-0.4, 0.0, 0.0]), True, storey),
    create_wall(12.5, "Exterior west upper", np.array([-0.4, 12.5, 0.0]), True, storey),
    create_wall(18.0, "Exterior east lower", np.array([41.2, 0.0, 0.0]), True, storey),
    create_wall(5.5, "Exterior east upper", np.array([41.2, 19.5, 0.0]), True, storey),
]

# Exterior exit positions for later IfcDoor / graph work; at present they are
# represented only by perimeter gaps, NOT IfcDoor or IfcOpeningElement objects.
EXITS = {
    "West exit": (0.0, 11.75),
    "South theatre exit": (4.75, 0.0),
    "South patient lobby exit": (29.75, 0.0),
    "North stair exit": (3.75, 25.0),
    "North recovery exit": (32.25, 25.0),
    "East exit": (41.0, 18.75),
}

model.write("hospital_level1_connected.ifc")
print(f"Wrote hospital_level1_connected.ifc: {len(ROOMS)} rooms, "
      f"{len(CORRIDORS)} corridor rectangles, {len(CONNECTIONS)} paired openings.")