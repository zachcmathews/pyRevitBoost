---
layout: default
title: Yank Parameters 
nav_order: 4
---

# Yank Parameters
Need to transfer parameters from equipment in a linked model to equipment in 
your model? Use pyRevitBoost's **Yank Parameters**.

## Instructions
1. Specify yank mappings within a YAML file. A template and explanation of 
fields can be found in the next section.
2. Select elements in your project which you have specified a yank mapping for.
2. Run **Yank Parameters** after ensuring an appropriate linked model is 
present.

## Specifying a mapping for yanking parameters from a linked model
A mapping takes the following form in YAML:
```yaml
-   from:
        model: MEC
        category: Mechanical Equipment
        phase: <current>
        exclude:
        - Designation = L
        parameters:
        - Designation
        - separator(-)
        - Mark
    to:
        category: Electrical Fixtures
        phase: <current>
        parameters:
        - Equipment ID
```

The field `from` specifies from where to yank parameters. It contains the 
following subfields:
- `model` = yank from linked models whose name contains `model`
- `category` = yank from this category of Revit elements
- `family` = yank from this family of Revit elements
- `type` = yank from this type of Revit elements
- `phase` = can be _&lt;current&gt;_ to use the phase of the current view or any 
specific phase. (e.g. _new construction_ or _existing_)
- `exclude` = when searching for elements to yank from exclude any element 
whose parameters match any in this list. You may use the following comparison 
operators: _= &gt; &lt; &gt;= &lt;=_.
- `parameters` = which parameters to yank values from. Specify a separator() 
between the parentheses to string together multiple parameters. Note that the 
specified parameters will be converted to strings (text) before being 
yanked into your model.

The field `to` specifies where to yank parameters to. It contains the 
following subfields:
- `category` = yank to elements of this category
- `family` = yank to elements of this family
- `type` = yank to elements of this type
- `phase` = can be _&lt;current&gt;_ to use the phase of the current view or any 
specific phase. (e.g. _new construction_ or _existing_)
- `parameters` = which parameters to transfer the yanked parameter values into.

You can find a template here: [YankParameters.yaml](/assets/templates/YankParameters.yaml)