---
layout: default
title: Reattach Wires
parent: Electrical
nav_order: 0
---

# Reattach Wires
Need to reattach wires that became disconnected due to copying, rotation, etc?
Use pyRevitBoost's **Reattach Wires** to reattach wires to the nearest 
electrical connectors.

## Instructions
1. Select wires within view that need to be reattached.
    - _Note: any other elements will be filtered out in preprocessing, so no 
need to fret if other elements are selected._
2. Run **Reattach Wires**.

_Note: any wires that run outside of the view will be ignored. This is 
intentionally done to prevent unseen side-effects._

_Note: if a wire's ends are too close together resulting in both ends trying 
to connect to the same electrical connector, then the command will fail._