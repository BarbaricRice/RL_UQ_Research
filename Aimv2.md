# Aim
To develop and validate a novel graph-based methodology for analysing egress within buildings by deriving travel distances from IFC models using IfcOpenShell.

# Objectives
- Establish an IFC model that produces a structured representation of a building consisting of walls, doors and rooms suitable for automated egress analysing using IfcOpenShell.
- Formulate a graph-based representation of the building egress network by abstracting IfcSpaces and IfcOpenings into nodes and edges of a graph.
- Develop and implement edge weightings utilising straight-line geometry distances that enable computation of combined egress paths within the IFC graph.
- Apply and evaluate pathfinding algorithms such as A*, for identifying critical egress paths within the building.
- Validate the proposed graph-based egress methodology by comparing the derived travel paths and calculated distances with results from Pathfinder evacuation simulations, and to assess its suitability for egress or travel distance computations.