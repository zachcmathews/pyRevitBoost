---
layout: default
title: CAD → Revit
nav_order: 1
---

# CAD → Revit
Got old CAD drawings lying around for your renovation projects?
Quickly place face-based and level-based Revit families using pyRevitBoost's 
**CAD → Revit** command.

## Instructions
1. Import AutoCAD drawing. _Insert → Import → Import CAD_
2. Verify positioning of imported AutoCAD drawing.
3. Specify mapping from CAD blocks to Revit family types using a tsv listing. 
See the following section for a template and run-down of each field.
4. Run **CAD → Revit**.

## Specifying a mapping from AutoCAD block to Revit family type
A mapping should follow the format listed below:

| Block  | Category          | Family                                    | Type                                       | Host                | Backup-Host                        | Origin-Offset        | Rotate-Origin-Offset | Orientation-Offset | Parameter      | Value |
|--------|-------------------|-------------------------------------------|--------------------------------------------|---------------------|------------------------------------|----------------------|----------------------|--------------------|----------------|-------|
| 2X4L   | Lighting Fixtures | TYPE A - RECESSED 2x4 LIGHT FIXTURE - LED | AX - Existing 4-lamp fixture               | Ceiling             | Reference Plane (01 LEVEL - 9'-0") |                      |                      |                    |                |       |
| LTX1C1 | Lighting Fixtures | TYPE X - CEILING MTD                      | X1C - EXIT SIGN SINGLE SIDED - AC ONLY     | Level               |                                    |                      |                      |                    | Fixture Height | 9' 0" |
| LTX1W1 | Lighting Fixtures | TYPE X - WALL MTD - UPDATED               | X1LW - EXIT SIGN WITH LAMP HEADS - BATTERY | Wall and Level (4') |                                    |                      |                      |                    |                |       |
| _U31   | Lighting Fixtures | TYPE A - RECESSED 2x4 LIGHT FIXTURE - LED | CX - Existing 2-lamp fixture               | Ceiling             | Reference Plane (01 LEVEL - 9'-0") | (3 5/8", 9 111/128") | -90°                 | -90°               |                |       |

Required fields:
- `Block` = name of AutoCAD block excluding everything after the last 
underscore that includes only numbers. (e.g. LTX1C1_2_31 becomes LTX1C1_2)
- `Category` = category of Revit family type
- `Family` = name of Revit family
- `Type` = name of Revit family
- `Host` = where to host placed family instance
    - one of  _Ceiling, Reference Plane, Level, Wall, Wall and Level_
    - if using _Wall_ or _Wall and Level_ then you must specify maximum 
distance to search for a nearby wall. (e.g. Wall and Level (4'))

Optional fields:
- `Backup-Host` = fall-through host if no ceiling is found
- `Origin-Offset` = how far the CAD block's origin is offset from the origin 
of the Revit family type. Specified in the form (x, y) where x,y are in the 
project's units of length
- `Rotate-Origin-Offset` = useful for correcting the *Origin-Offset* if you 
measured after rotating the CAD import
- `Orientation-Offset` = how much the CAD block is rotated with respect to 
the placed Revit family. (i.e. some families may be placed longitidunally 
where the block may have been placed latitudinally)
- `Parameter` and `Value` = set value of parameter name to value. (e.g. 
set height after placing level-based families)

Find a template here: [CADToRevit.txt](/assets/templates/CADToRevit.txt)

The template can be modified using Excel or Google Sheets and then saved as a
tab-separated values file with .txt extension.