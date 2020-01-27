# SDK_manager

Originally based off of one of Judd Simantov’s [facial rigging](https://vimeo.com/user5566082) workflows 
using joints and SDK’s to craft facial shapes with the power of blendshapes 
but the control of joints and weighting.

The toolset I’d like to make is based off of SuperCrumbly’s [abFaceRig](https://www.youtube.com/watch?v=NnECICrGg1k&index=38&list=WL&t=977s) toolset. 
It was designed to work hand in hand with Judd’s SDK workflow. 

---
## Installation
1. Clone the latest [mGear Repo](https://github.com/mgear-dev/mgear_dist) to your machine and install as normal.
2. Closne SDK_manager to  **\mGear\scripts\mgear\rigbits**
3. Inside "\SDK_manager\components\" copy "sdk_control_01" to "mgear\shifter_classic_components".
4. You should now be able to call SDK manager inside maya using this:
```
from mgear.rigbits.SDK_manager import SDK_manager_ui as SDKM_UI
reload(SDKM_UI)

try:
    if manager_ui:
        manager_ui.closeEvent()
except:
    pass
    
manager_ui = SDKM_UI.SDK_Manager_Dialog()
manager_ui.show(dockable=True)
```

----
## Pros

* Can get same results as Blendshape Based face Rig. Giving the rigger extreme control over every single shape.
* Can expose tweak control over every joint to Anim, This might be an alternative to shape fixing as they would have the same level of control.
* If implemented correctly can fit into the rebuild workflow, allowing pivots and controllers to be altered without destroying rig work.
* Can export one characters weight map, Guide, SDK’s and import to another character as a base to work from. Making time to rig less.
* Can Add blendshapes on top of  things for further deformation
* Some code base for this method has already been written. 
* Low poly character faces work to this method’s favour as less SDK components need to be made, making the rig lighter. 

## Cons

* Need to build tools to integrate it with our workflow + pipeline (Time)
* 1000’s of SDK’s are slower than blendshapes. (Rig performance) (This needs to be TESTED.)
* Controls might feel “floaty”, but the effect can be minimised.
* Lips system will need an alternative. (Ribbon rig)
* Rigger will need to be taught how to use the tools. 


----

### Component

A mGear component will need to be made. Should be a simple setup. Can be done in half  a day by anyone who has made a component before.

---
### Lip ribbon
[Advanced Ribbon Rig Demo](https://www.youtube.com/watch?v=Qz7R3i5pnBU)

----
### SDK Workflow:

Each component looks like this:
* ROOT
  * SDKBOX
    * Anim Tweak
      * Joint driver Grp

When one is selected, a  function will be needed to find all of the other bits. Ie: select the anim Tweak, the set SDK tool will need to set SDK’s on the SDK box, not anim tweak. Given one piece of information, it must be able to return all of the others. 

SDK’s are set on the SDK box, driven by normal driver controls using custom made tools for the workflow.

Blendshapes can also be attached to the driver controls in cases where further deformation is needed and cannot be achieved with only the SDK boxes and weight painting. 


