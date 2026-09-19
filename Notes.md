# 20/04/2026 Notes
- IfcOpenShell very very time consuming and basic. Very steep learning curve
- Archicad a lot easier to navigate and manipulate
- Missing a lot of parameters? Do they need to be defined?


# Research Title
- Investgating Simple Fire Evacuation Analysis using BIM
- Developing a Novel Technique to Evaluate Simple Fire Evacuation within the BIM Environment

# 25/04/2026 Notes
- Develop a proper hierarchy for objects
- how to link an opening to two rooms (spaces)?
- Create functions for these things


# 14/09/2026 Brainstorming Notes
- Use topology of graph to do risk analysis
    - which nodes have high degree
- node clusters
- smoke movement/zone models for rooms
## thoughts
- if nodes were represented by the openings of the building:
    - weights would be distance between openings
    - can't see information about the room itself
    - basically only limited to openings and relationship to openings

- if nodes were represented by rooms:
    - rooms can have openings incorporated in them
    - information about the room can be extracted

- anything further becomes a bit too convoluted and requires manual processing
- defeats the purpose of feasibility of IFC application

# ideas
- graph is now established. it's a non directional graph, but technically it is directional for a specific path
- clusters of graph. can see that there are two clusters in this example, this can form part of the fire safety strategy i.e. criticality of protecting these corridors
- distance to the "node bridges". this could be assessed
- do a zone model to assess losing tenability within the corridors. can extract the information from ifc model
- 1. identify critical room. 2. identify worst room to egress to it. 3. zone model to assess egress to this room.