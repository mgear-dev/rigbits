"""Rigbits brow rigger tool"""
"""Based on Rigbits lips rigger tool"""
""" Brow rigger test -> Rabidrat.pl Krzysztof Marcinowski"""
import json
from functools import partial

import mgear.core.pyqt as gqt
import pymel.core as pm
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from mgear.vendor.Qt import QtCore, QtWidgets
from pymel.core import datatypes

from mgear import rigbits
from mgear.core import meshNavigation, curve, applyop, primitive, icon
from mgear.core import transform, attribute, skin, pickWalk

from . import lib
from . import helpers
from . import constraints


def rig(eLoop,
        namePrefix,
        thickness,
        mainDivisions,
        secDivisions,
        doSkin,
        secondaryCtlCheck,
        symmetryMode,
        side,
        rigidLoops,
        falloffLoops,
        c_BrowJnt=None,
        l_BrowJnt=None,
        r_BrowJnt=None,
        l_CtlParent=None,
        r_CtlParent=None,
        parent=None,
        ctlName="ctl"):
    ######
    # Var
    ######
    FRONT_OFFSET = .02
    NB_ROPE = 10
    midDivisions = 3

    doSkin = False  # skinning will be disabled by default.

    ####################
    # Validate Data
    # ##################
    eLoops = {}  # collect edge loops and it's sides in DICT
    controls_collect = []  # collect parent controls
    joints_collect = []  # collect parent joints

    # divisions
    mainDivisions = int(mainDivisions)
    secDivisions = int(secDivisions)
    # Edges

    if eLoop:
        try:
            eLoop = [pm.PyNode(e) for e in eLoop.split(",")]
        except pm.MayaNodeError:
            pm.displayWarning(
                "Some of the edges listed in edge loop can not be found")
            return
    # Geo
        geo = pm.listRelatives(eLoop[0], parent=True)[0]
        geoTransform = pm.listRelatives(geo, fullPath=False, parent=True)[0]

    else:
        pm.displayWarning("Please set the edge loop first")
        return

    # symmetry mode
    # 0 => ON  1 = > OFF
    if symmetryMode == 0:
        # symmetry is on, collect required data
        # mirror edge loop
        mLoop = []
        for edge in eLoop:
            mEdge = meshNavigation.find_mirror_edge(geoTransform,
                                                    edge.indices()[0])
            mLoop.append(mEdge)

        if len(mLoop) != len(eLoop):
            pm.displayWarning(
                "Mesh is not symmetrical, please fix it or create temp GEO")
            return

        # set side
        if eLoop[0].getPoint(0, space='world') > 0:
            # left
            side = "L"
            l_Loop = eLoop
            r_Loop = mLoop
        else:
            # right
            side = "R"
            l_Loop = mLoop
            r_Loop = eLoop

        # get edges for center module
        p1 = l_Loop[0].getPoint(0, space='world')[0]
        p2 = l_Loop[-1].getPoint(0, space='world')[0]
        if p1 < p2:
            l_inner = l_Loop[0]
        else:
            l_inner = l_Loop[-1]
        p1 = r_Loop[0].getPoint(0, space='world')[0]
        p2 = r_Loop[-1].getPoint(0, space='world')[0]

        if p1 > p2:
            r_inner = r_Loop[0]
        else:
            r_inner = r_Loop[-1]

        # center segment
        c_Loop = [pm.PyNode(e) for e in pm.polySelect(
                  geoTransform,
                  edgeLoopPath=(l_inner.indices()[0],
                                r_inner.indices()[0]),
                  ass=True,
                  ns=True)
                  if pm.PyNode(e) not in l_Loop and pm.PyNode(e) not in r_Loop]
        eLoops = dict(zip(["L", "R", "C"], [l_Loop, r_Loop, c_Loop]))

    else:
        # symmetry is off
        sideOptions = {0: "C",
                       1: "L",
                       2: "R"}
        if side:
            side = sideOptions[side]
        else:
            side = "C"
        # set
        c_Loop = eLoop
        eLoops = dict(zip([side], [c_Loop]))

    # parent node
    if parent:
        try:
            parentNode = pm.PyNode(parent)
        except pm.MayaNodeError:
            pm.displayWarning(
                "Static rig parent: %s can not be found" % parentNode)
            return

    # parent joints
    # 0 => ON  1 = > OFF
    # center main joint parent
    if c_BrowJnt:
        try:
            c_BrowJnt = pm.PyNode(c_BrowJnt)
            joints_collect.append(c_BrowJnt)
        except pm.MayaNodeError:
            pm.displayWarning(
                "Mid parent joint: %s can not be found" % c_BrowJnt)
            return
    else:
        pm.displayWarning("Main parent joints is required. It would be used"
                          " as main parent if side parents are not set.")
        return

    if symmetryMode == 0:
        if l_BrowJnt:
            try:
                l_BrowJnt = pm.PyNode(l_BrowJnt)
                joints_collect.append(l_BrowJnt)
            except pm.MayaNodeError:
                pm.displayWarning(
                    "Left parent joint: %s can not be found" % l_BrowJnt)
                return
        else:
            pm.displayWarning(
                "With symmetry mode you need to set the left parent joint.")
            return

        if r_BrowJnt:
            try:
                r_BrowJnt = pm.PyNode(r_BrowJnt)
                joints_collect.append(r_BrowJnt)
            except pm.MayaNodeError:
                pm.displayWarning(
                    "Right parent joint: %s can not be found." % r_BrowJnt)
                return
        else:
            try:
                r_BrowJnt = pickWalk.getMirror(l_BrowJnt)[0]
                joints_collect.append(r_BrowJnt)
            except pm.MayaNodeError:
                pm.displayWarning(
                    "Right parent joint: "
                    "%s can not be found. Please set it manually." % r_BrowJnt)
                return

    # parent controls
    if l_CtlParent:
        try:
            l_CtlParent = pm.PyNode(l_CtlParent)
            controls_collect.append(l_CtlParent)
        except pm.MayaNodeError:
            pm.displayWarning(
                "Right (Left) ctl: %s can not be found" % l_CtlParent)
            return
    else:
        l_CtlParent = l_BrowJnt

    if symmetryMode == 0:
        if r_CtlParent:
            try:
                r_CtlParent = pm.PyNode(r_CtlParent)
                controls_collect.append(r_CtlParent)
            except pm.MayaNodeError:
                pm.displayWarning(
                    "Right ctl: %s can not be found" % r_CtlParent)
                return
        else:
            r_CtlParent = r_BrowJnt

    ##################
    # Helper functions
    # ##################

    def setName(name, side="C", idx=None):
        namesList = [namePrefix, side, name]
        if idx is not None:
            namesList[1] = side + str(idx)
        name = "_".join(namesList)
        return name

    def getSide(name):
        # name = name.strip(namePrefix)

        if namePrefix + "_L_" in name.name():
            side = "L"
        elif namePrefix + "_R_" in name.name():
            side = "R"
        else:
            side = "C"
        return side

    # check if the rig already exist in the current scene
    if pm.ls(setName("root", side)):
        pm.displayWarning("The object %s already exist in the scene. Please "
                          "choose another name prefix" % setName("root"))
        return

    ###################
    # Root creation
    ###################
    if symmetryMode == 0:
        rootSide = "C"
    else:
        rootSide = side
    brows_root = primitive.addTransform(None,
                                        setName("root", rootSide))
    browsCrv_root = primitive.addTransform(brows_root,
                                           setName("crvs", rootSide))
    browsHooks_root = primitive.addTransform(brows_root,
                                             setName("hooks", rootSide))
    browsRope_root = primitive.addTransform(brows_root,
                                            setName("rope", rootSide))
    browsControl_root = primitive.addTransform(brows_root,
                                               setName("controls", rootSide))

    #####################
    # Groups
    #####################
    try:
        ctlSet = pm.PyNode("rig_controllers_grp")
    except pm.MayaNodeError:
        pm.sets(n="rig_controllers_grp", em=True)
        ctlSet = pm.PyNode("rig_controllers_grp")
    try:
        defset = pm.PyNode("rig_deformers_grp")
    except pm.MayaNodeError:
        pm.sets(n="rig_deformers_grp", em=True)
        defset = pm.PyNode("rig_deformers_grp")

    # ###################
    # Collect data
    #####################
    # store the closest vertex by curv cv index. To be use fo the auto skining
    # browsMainCrv_closestVtxList = []

    # temp parent memory
    # parentsMemory = []
    l_hookMem = []
    r_hookMem = []
    c_hookMem = []

    # collect curves
    rigCurves = []
    mainCtlCurves = []
    mainCtlUpvs = []
    secondaryCurves = []
    mainRopes = []
    mainRopeUpvs = []
    mainCurveUpvs = []
    mainCurves = []

    # collect objects
    mainControls = []
    mainUpvs = []
    secondaryControls = []
    secondaryUpvs = []
    allJoints = []
    closestVtxsList = []

    # ###############################
    # Create curves and controls
    #################################
    for side, loop in eLoops.items():

        # create poly based curve for each part
        mainCurve = curve.createCuveFromEdges(loop,
                                              setName("main_crv", side),
                                              parent=browsCrv_root)
        # collect main poly based curve
        mainCurves.append(mainCurve)
        rigCurves.append(mainCurve)

        # offset main brow curve
        cvs = mainCurve.getCVs(space='world')
        for i, cv in enumerate(cvs):
            closestVtx = meshNavigation.getClosestVertexFromTransform(geo, cv)
            closestVtxsList.append(closestVtx)
            if i == 0:
                # we know the curv starts from right to left
                offset = [cv[0] - thickness, cv[1], cv[2] - thickness]
            elif i == len(cvs) - 1:
                offset = [cv[0] + thickness, cv[1], cv[2] - thickness]
            else:
                offset = [cv[0], cv[1] + thickness, cv[2]]
            mainCurve.setCV(i, offset, space='world')

        # ###################
        # Get control positions
        #####################
        if symmetryMode == 0:  # 0 means ON
            if side is "C":  # middle segment should be divided into 3 points.
                mainCtrlPos = helpers.divideSegment(mainCurve, midDivisions)
            else:
                mainCtrlPos = helpers.divideSegment(mainCurve, mainDivisions)
            if secondaryCtlCheck is True and side is not "C":
                # get secondary controls position
                secCtrlPos = helpers.divideSegment(mainCurve, secDivisions)

        else:
            print mainCurve
            print mainDivisions
            mainCtrlPos = helpers.divideSegment(mainCurve, mainDivisions)
            if secondaryCtlCheck is True:
                # get secondary controls position

                secCtrlPos = helpers.divideSegment(mainCurve, secDivisions)
        # ###################
        # Set control options
        #####################
        # points are sorted from X+, based on this set required options
        mainCtrlOptions = []
        secCtrlOptions = []

        # main control options
        for i, ctlPos in enumerate(mainCtrlPos):
            controlType = "square"

            if i is 0:
                if side is "L":
                    posPrefix = "in"
                if side is "R":
                    posPrefix = "out"
                if side is "C":
                    posPrefix = "out_R"
                    if symmetryMode is 0:
                        controlType = "npo"

            elif i is (len(mainCtrlPos) - 1):
                if side is "L":
                    posPrefix = "out"
                if side is "R":
                    posPrefix = "in"
                if side is "C":
                    posPrefix = "out_L"
                    if symmetryMode == 0:
                        controlType = "npo"
            else:
                posPrefix = "mid_0" + str(i)

            if posPrefix is "in":
                if side is "L":
                    tPrefix = [posPrefix + "_tangent", posPrefix]
                    tControlType = ["sphere", controlType]
                    tControlSize = [0.85, 1.0]
                if side is "R":
                    tPrefix = [posPrefix, posPrefix + "_tangent"]
                    tControlType = [controlType, "sphere"]
                    tControlSize = [1.0, 0.85]

                options = [tPrefix[1],
                           side,
                           tControlType[1],
                           6,
                           tControlSize[1],
                           [],
                           ctlPos]
                mainCtrlOptions.append(options)

                options = [tPrefix[0],
                           side,
                           tControlType[0],
                           6,
                           tControlSize[0],
                           [],
                           ctlPos]
                mainCtrlOptions.append(options)

            elif "out_" in posPrefix and symmetryMode == 1:
                if posPrefix is "out_L":
                    tPrefix = [posPrefix + "_tangent", posPrefix]
                    tControlType = ["sphere", controlType]
                    tControlSize = [0.85, 1.0]
                if posPrefix is "out_R":
                    tPrefix = [posPrefix, posPrefix + "_tangent"]
                    tControlType = [controlType, "sphere"]
                    tControlSize = [1.0, 0.85]

                options = [tPrefix[0],
                           side,
                           tControlType[0],
                           6,
                           tControlSize[1],
                           [],
                           ctlPos]
                mainCtrlOptions.append(options)
                options = [tPrefix[1],
                           side,
                           tControlType[1],
                           6,
                           tControlSize[0],
                           [],
                           ctlPos]
                mainCtrlOptions.append(options)

            else:
                options = [posPrefix,
                           side,
                           controlType,
                           6,
                           1.0,
                           [],
                           ctlPos]
                mainCtrlOptions.append(options)

        # secondary control options
        if secondaryCtlCheck is True:
            if symmetryMode == 0:  # 0 means ON
                secSideRange = "LR"
            else:
                secSideRange = "CLR"

            if side in secSideRange:
                controlType = "circle"
                for i, ctlPos in enumerate(secCtrlPos):
                    posPrefix = "sec_0" + str(i)
                    options = [posPrefix,
                               side,
                               controlType,
                               13,
                               0.55,
                               [],
                               ctlPos]
                    secCtrlOptions.append(options)

        params = ["tx", "ty", "tz"]
        distSize = 1

        if secondaryCtlCheck is True:
            controlOptionList = [mainCtrlOptions, secCtrlOptions]
        else:
            controlOptionList = [mainCtrlOptions]

        # ###################
        # Create controls from option lists.
        #####################
        localCtlList = []
        localSecCtlList = []
        for j, ctlOptions in enumerate(controlOptionList):
            # set status for main controllers
            if j is 0:
                testName = setName("mainControls")
                controlStatus = 0  # main controls
                try:
                    controlParentGrp = pm.PyNode(testName)
                except:
                    controlParentGrp = primitive.addTransform(
                        browsControl_root, setName("mainControls"))
            # set status for secondary controllers
            else:
                testName = setName("secondaryControls")
                controlStatus = 1  # secondary controls
                try:
                    controlParentGrp = pm.PyNode(testName)
                except:
                    controlParentGrp = primitive.addTransform(
                        browsControl_root, setName("secondaryControls"))

            # Create controls for each point position.
            for i, point in enumerate(ctlOptions):
                pm.progressWindow(e=True,
                                  step=1,
                                  status='\nCreating control for%s' % point)
                oName = ctlOptions[i][0]
                oSide = ctlOptions[i][1]
                o_icon = ctlOptions[i][2]
                color = ctlOptions[i][3]
                wd = ctlOptions[i][4]
                oPar = ctlOptions[i][5]
                point = ctlOptions[i][6]

                position = transform.getTransformFromPos(point)

                npo = primitive.addTransform(controlParentGrp,
                                             setName("%s_npo" % oName, oSide),
                                             position)

                npoBuffer = primitive.addTransform(
                    npo,
                    setName("%s_bufferNpo" % oName, oSide),
                    position)
                # Create casual control
                if o_icon is not "npo":
                    ctl = icon.create(
                        npoBuffer,
                        setName("%s_%s" % (oName, ctlName), oSide),
                        position,
                        icon=o_icon,
                        w=wd,
                        d=wd,
                        ro=datatypes.Vector(1.57079633, 0, 0),
                        po=datatypes.Vector(0, 0, .07 * distSize),
                        color=color)
                # Create buffer node instead
                else:
                    ctl = primitive.addTransform(
                        npoBuffer,
                        setName("%s_HookNpo" % oName, oSide),
                        position)

                cname_split = ctlName.split("_")
                if len(cname_split) == 2 and cname_split[-1] == "ghost":
                    pass
                else:
                    pm.sets(ctlSet, add=ctl)
                attribute.setKeyableAttributes(ctl, params + oPar)

                # Create up vectors for each control
                upv = primitive.addTransform(ctl,
                                             setName("%s_upv" % oName, oSide),
                                             position)
                upv.attr("tz").set(FRONT_OFFSET)

                # Collect local (per curve) and global controllers list
                if controlStatus == 0:
                    mainControls.append(ctl)
                    mainUpvs.append(upv)
                    localCtlList.append(ctl)

                if controlStatus == 1:
                    secondaryControls.append(ctl)
                    secondaryUpvs.append(upv)
                    localSecCtlList.append(ctl)

                if oSide == "R":
                    npo.attr("sx").set(-1)

                # collect hook npos'
                if side is "L" and "in" in oName:
                    l_hookMem.append(ctl)
                if side is "R" and "in" in oName:
                    r_hookMem.append(ctl)
                if side is "C":
                    c_hookMem.append(ctl)

            pm.progressWindow(e=True, endProgress=True)

            #####################
            # Curves creation
            #####################

            if controlStatus == 0:  # main controls
                mainCtlCurve = helpers.addCnsCurve(
                    browsCrv_root,
                    setName("mainCtl_crv", side),
                    localCtlList,
                    3)
                rigCurves.append(mainCtlCurve[0])
                mainCtlCurves.append(mainCtlCurve[0])

                # create upvector curve to drive secondary control
                if secondaryCtlCheck is True:
                    if side in secSideRange:
                        mainCtlUpv = helpers.addCurve(
                            browsCrv_root,
                            setName("mainCtl_upv", side),
                            localCtlList,
                            3)
                        # connect upv curve to mainCrv_ctl driver node.
                        pm.connectAttr(
                            mainCtlCurve[1].attr("outputGeometry[0]"),
                            mainCtlUpv.getShape().attr("create"))

                        # offset upv curve
                        cvs = mainCtlUpv.getCVs(space="world")
                        for i, cv in enumerate(cvs):
                            offset = [cv[0], cv[1], cv[2] + FRONT_OFFSET]
                            mainCtlUpv.setCV(i, offset, space='world')
                        # collect mainCrv upv
                        rigCurves.append(mainCtlUpv)
                        mainCtlUpvs.append(mainCtlUpv)

            # create secondary control curve.
            if controlStatus == 1:
                if side in secSideRange:
                    secondaryCtlCurve = helpers.addCnsCurve(
                        browsCrv_root,
                        setName("secCtl_crv", side),
                        localSecCtlList,
                        3)
                    secondaryCurves.append(secondaryCtlCurve[0])
                    rigCurves.append(secondaryCtlCurve[0])

        # create upvector / rope curves
        mainRope = curve.createCurveFromCurve(
            mainCurve,
            setName("mainRope", side),
            nbPoints=NB_ROPE,
            parent=browsCrv_root)

        rigCurves.append(mainRope)
        mainRopes.append(mainRope)
        ###
        mainRope_upv = curve.createCurveFromCurve(
            mainCurve,
            setName("mainRope_upv", side),
            nbPoints=NB_ROPE,
            parent=browsCrv_root)

        rigCurves.append(mainRope_upv)
        mainRopeUpvs.append(mainRope_upv)
        ###
        mainCrv_upv = curve.createCurveFromCurve(
            mainCurve,
            setName("mainCrv_upv", side),
            nbPoints=7,
            parent=browsCrv_root)

        rigCurves.append(mainCrv_upv)
        mainCurveUpvs.append(mainCrv_upv)

    # offset upv curves
        for crv in [mainRope_upv, mainCrv_upv]:
            cvs = crv.getCVs(space="world")
            for i, cv in enumerate(cvs):
                # we populate the closest vertext list here to skipt the first
                # and latest point
                offset = [cv[0], cv[1], cv[2] + FRONT_OFFSET]
                crv.setCV(i, offset, space='world')

    # hide curves
    for crv in rigCurves:
        crv.attr("visibility").set(False)

    ###########################################
    # Connecting controls
    ###########################################
    if parent:
        try:
            if isinstance(parent, basestring):
                parent = pm.PyNode(parent)
            parent.addChild(brows_root)
        except pm.MayaNodeError:
            pm.displayWarning("The brow rig can not be parent to: %s. Maybe "
                              "this object doesn't exist." % parent)

    # Reparent controls

    for ctl in mainControls:
        ctl_side = getSide(ctl)

        if ctl_side is "L":
            if "in_tangent_ctl" in ctl.name():
                l_child = ctl
            if "in_ctl" in ctl.name():
                l_parent = ctl

        if ctl_side is "R":
            if "in_tangent_ctl" in ctl.name():
                r_child = ctl
            if "in_ctl" in ctl.name():
                r_parent = ctl

        if symmetryMode == 0:  # 0 means ON
            if ctl_side is "C":
                if "out_R" in ctl.name():
                    c_outR = ctl
                if "out_L" in ctl.name():
                    c_outL = ctl
                if "mid_" in ctl.name():
                    c_mid = ctl
        else:
            if ctl_side is "C":
                if "out_R_ctl" in ctl.name():
                    c_outR = ctl
                if "out_L_ctl" in ctl.name():
                    c_outL = ctl

                if "out_R_tangent" in ctl.name():
                    t_outR = ctl
                if "out_L_tangent" in ctl.name():
                    t_outL = ctl

    # parent controls
    if symmetryMode == 0:
        # inside parents
        pm.parent(l_child.getParent(2), l_parent)
        pm.parent(r_child.getParent(2), r_parent)
        constraints.matrixBlendConstraint([r_parent, l_parent],
                                          c_mid.getParent(2),
                                          [0.5, 0.5],
                                          't',
                                          True,
                                          c_mid)
        constraints.matrixConstraint(r_parent,
                                     c_outR.getParent(2),
                                     'srt',
                                     True)
        constraints.matrixConstraint(l_parent,
                                     c_outL.getParent(2),
                                     'srt',
                                     True)
        constraints.matrixConstraint(c_BrowJnt,
                                     c_mid.getParent(2),
                                     'rs',
                                     True)
        for ctl in mainControls:
            ctl_side = getSide(ctl)

            if ctl_side is "L" and "_tangent" not in ctl.name():
                constraints.matrixConstraint(l_CtlParent,
                                             ctl.getParent(2),
                                             'srt',
                                             True)
            if ctl_side is "R" and "_tangent" not in ctl:
                constraints.matrixConstraint(r_CtlParent,
                                             ctl.getParent(2),
                                             'srt',
                                             True)
    else:
        ctl_side = getSide(mainControls[0])

        if ctl_side is "L":
            pm.parent(l_child.getParent(2), l_parent)
        if ctl_side is "R":
            pm.parent(r_child.getParent(2), r_parent)
        if ctl_side is "C":
            pm.parent(t_outR.getParent(2), c_outR)
            pm.parent(t_outL.getParent(2), c_outL)

        for ctl in mainControls:
            if "_tangent" not in ctl.name():
                constraints.matrixConstraint(l_CtlParent,
                                             ctl.getParent(2),
                                             'srt',
                                             True)

    # Attach secondary controls to main curve
    if secondaryCtlCheck is True:
        secControlsMerged = []
        if symmetryMode == 0:  # 0 means ON
            tempMainCtlCurves = [crv for crv in mainCtlCurves
                                 if getSide(crv) in "LR"]
            tempMainUpvCurves = [crv for crv in mainCtlUpvs
                                 if getSide(crv) in "LR"]
            leftSec = []
            rightSec = []
            for secCtl in secondaryControls:
                if getSide(secCtl) is "L":
                    # connect secondary controla rotate/scale to l_CtlParent.
                    constraints.matrixConstraint(l_CtlParent,
                                                 secCtl.getParent(2),
                                                 'rs',
                                                 True)
                    leftSec.append(secCtl)

                if getSide(secCtl) is "R":
                    # connect secondary controla rotate/scale to l_CtlParent.
                    constraints.matrixConstraint(r_CtlParent,
                                                 secCtl.getParent(2),
                                                 'rs',
                                                 True)
                    rightSec.append(secCtl)

            secControlsMerged.append(rightSec)
            secControlsMerged.append(leftSec)

        else:
            tempMainCtlCurves = mainCtlCurves
            tempMainUpvCurves = mainCtlUpvs
            secControlsMerged.append(secondaryControls)

            for secCtl in secondaryControls:
                constraints.matrixConstraint(l_CtlParent,
                                             secCtl.getParent(2),
                                             'rs',
                                             True)

        # create hooks on the main ctl curve
        for j, crv in enumerate(secondaryCurves):
            side = getSide(crv)

            lvlType = 'transform'
            cvs = crv.getCVs(space="world")

            for i, cv in enumerate(cvs):

                oTransUpV = pm.PyNode(pm.createNode(
                    lvlType,
                    n=setName("secNpoUpv", side, idx=str(i).zfill(3)),
                    p=browsHooks_root,
                    ss=True))

                oTrans = pm.PyNode(pm.createNode(
                    lvlType,
                    n=setName("secNpo", side, idx=str(i).zfill(3)),
                    p=browsHooks_root, ss=True))

                oParam, oLength = curve.getCurveParamAtPosition(crv, cv)
                uLength = curve.findLenghtFromParam(crv, oParam)
                u = uLength / oLength

                # create motion paths transforms on main ctl curves
                applyop.pathCns(oTransUpV,
                                tempMainUpvCurves[j],
                                cnsType=False,
                                u=u,
                                tangent=False)
                cns = applyop.pathCns(
                    oTrans, tempMainCtlCurves[j], cnsType=False, u=u, tangent=False)

                cns.setAttr("worldUpType", 1)
                cns.setAttr("frontAxis", 0)
                cns.setAttr("upAxis", 1)

                pm.connectAttr(oTransUpV.attr("worldMatrix[0]"),
                               cns.attr("worldUpMatrix"))

                # connect secondary control to oTrans hook.
                constraints.matrixConstraint(oTrans,
                                             secControlsMerged[j][i].getParent(2),
                                             't',
                                             True)

    ##################
    # Wires and connections
    ##################

    # set drivers
    crvDrivers = []
    if secondaryCtlCheck is True:
        if symmetryMode == 0:
            crv = [crv for crv in mainCtlCurves if getSide(crv) is "C"]
            crvDrivers.append(crv[0])

            crv = [crv for crv in secondaryCurves]
            for c in crv:
                crvDrivers.append(c)
        else:
            crvDrivers = secondaryCurves

    else:
        crvDrivers = mainCtlCurves

    for i, drv in enumerate(crvDrivers):
        pm.wire(mainCurves[i], w=drv, dropoffDistance=[0, 1000])
        pm.wire(mainCurveUpvs[i], w=drv, dropoffDistance=[0, 1000])
        pm.wire(mainRopes[i], w=drv, dropoffDistance=[0, 1000])
        pm.wire(mainRopeUpvs[i], w=drv, dropoffDistance=[0, 1000])
    # ###########################################
    # Joints
    ###########################################
    lvlType = "transform"

    for j, crv in enumerate(mainCurves):
        cvs = crv.getCVs(space="world")
        side = getSide(crv)

        if symmetryMode == 0:  # 0 means ON
            if side is "L":
                browJoint = l_BrowJnt
            if side is "R":
                browJoint = r_BrowJnt
            if side is "C":
                browJoint = c_BrowJnt
        else:
            browJoint = c_BrowJnt

        for i, cv in enumerate(cvs):

            oTransUpV = pm.PyNode(pm.createNode(
                lvlType,
                n=setName("browRopeUpv", idx=str(i).zfill(3)),
                p=browsRope_root,
                ss=True))

            oTrans = pm.PyNode(
                pm.createNode(lvlType,
                              n=setName("browRope", side, idx=str(i).zfill(3)),
                              p=browsRope_root, ss=True))

            oParam, oLength = curve.getCurveParamAtPosition(mainRopeUpvs[j], cv)
            uLength = curve.findLenghtFromParam(mainRopes[j], oParam)
            u = uLength / oLength

            applyop.pathCns(
                oTransUpV, mainRopeUpvs[j], cnsType=False, u=u, tangent=False)

            cns = applyop.pathCns(
                oTrans, mainRopes[j], cnsType=False, u=u, tangent=False)

            cns.setAttr("worldUpType", 1)
            cns.setAttr("frontAxis", 0)
            cns.setAttr("upAxis", 1)

            pm.connectAttr(oTransUpV.attr("worldMatrix[0]"),
                           cns.attr("worldUpMatrix"))

            jnt = rigbits.addJnt(oTrans, noReplace=True, parent=browJoint)
            allJoints.append(jnt)
            pm.sets(defset, add=jnt)

    for crv in mainCurves:
        pm.delete(crv)

    ###########################################
    # Auto Skinning
    ###########################################
    if doSkin:
        print allJoints
        # base skin
        if c_BrowJnt:
            try:
                c_BrowJnt = pm.PyNode(c_BrowJnt)
            except pm.MayaNodeError:
                pm.displayWarning(
                    "Auto skin aborted can not find %s " % c_BrowJnt)
                return

        # Check if the object has a skinCluster
        objName = pm.listRelatives(geo, parent=True)[0]

        skinCluster = skin.getSkinCluster(objName)

        if not skinCluster:
            skinCluster = pm.skinCluster(joints_collect,
                                         geo,
                                         tsb=True,
                                         nw=2,
                                         n='skinClsBrow')

        totalLoops = rigidLoops + falloffLoops

        # we set the first value 100% for the first initial loop
        skinPercList = [1.0]
        # we expect to have a regular grid topology
        for r in range(rigidLoops):
            for rr in range(2):
                skinPercList.append(1.0)
        increment = 1.0 / float(falloffLoops)
        # we invert to smooth out from 100 to 0
        inv = 1.0 - increment
        for r in range(falloffLoops):
            for rr in range(2):
                if inv < 0.0:
                    inv = 0.0
                skinPercList.append(inv)
            inv -= increment

        # this loop add an extra 0.0 indices to avoid errors
        for r in range(100):
            for rr in range(2):
                skinPercList.append(0.0)

        pm.progressWindow(title='Auto skinning process',
                          progress=0,
                          max=len(allJoints))

        vertexRowsList = []

        for side, loop in eLoops.items():
            extr_v = meshNavigation.getExtremeVertexFromLoop(loop)
            vertexList = extr_v[5]

            vertexLoopList = meshNavigation.getConcentricVertexLoop(
                vertexList,
                totalLoops)
            vertexRowList = meshNavigation.getVertexRowsFromLoops(
                vertexLoopList)
            vertexRowsList += vertexRowList

            # allJoints
            # closestVtxsList
        for i, jnt in enumerate(allJoints):
            print jnt
            pm.progressWindow(e=True, step=1, status='\nSkinning %s' % jnt)
            skinCluster.addInfluence(jnt, weight=0)
            v = closestVtxsList[i]
            for row in vertexRowsList:
                if v in row:
                    for i, rv in enumerate(row):
                        # find the deformer with max value for each vertex
                        w = pm.skinPercent(skinCluster,
                                           rv,
                                           query=True,
                                           value=True)
                        transJoint = pm.skinPercent(skinCluster,
                                                    rv,
                                                    query=True,
                                                    t=None)
                        max_value = max(w)
                        max_index = w.index(max_value)

                        perc = skinPercList[i]
                        t_value = [(jnt, perc),
                                   (transJoint[max_index], 1.0 - perc)]
                        pm.skinPercent(skinCluster,
                                       rv,
                                       transformValue=t_value)
        pm.progressWindow(e=True, endProgress=True)

##########################################################
# Brows Rig UI
##########################################################


class ui(MayaQWidgetDockableMixin, QtWidgets.QDialog):

    valueChanged = QtCore.Signal(int)

    def __init__(self, parent=None):
        super(ui, self).__init__(parent)

        self.filter = "Brows Rigger Configuration .lips (*.brows)"

        self.create()

    def create(self):

        self.setWindowTitle("Brows Rigger")
        self.setWindowFlags(QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, 1)

        self.create_controls()
        self.create_layout()
        self.create_connections()

    def create_controls(self):

        # Geometry input controls
        self.geometryInput_group = QtWidgets.QGroupBox("Geometry Input")
        self.edgeloop_label = QtWidgets.QLabel("Brow Edge Loop:")
        self.edgeloop_lineEdit = QtWidgets.QLineEdit()
        self.edgeloop_button = QtWidgets.QPushButton("<<")

        # Name prefix
        self.prefix_group = QtWidgets.QGroupBox("Name Prefix")
        self.prefix_lineEdit = QtWidgets.QLineEdit()
        self.prefix_lineEdit.setText("brow")

        # control extension
        self.control_group = QtWidgets.QGroupBox("Control Name Extension")
        self.control_lineEdit = QtWidgets.QLineEdit()
        self.control_lineEdit.setText("ctl")

        # Topological Autoskin
        self.topoSkin_group = QtWidgets.QGroupBox("Skin")
        self.rigidLoops_label = QtWidgets.QLabel("Rigid Loops:")
        self.rigidLoops_value = QtWidgets.QSpinBox()
        self.rigidLoops_value.setRange(0, 30)
        self.rigidLoops_value.setSingleStep(1)
        self.rigidLoops_value.setValue(5)
        self.falloffLoops_label = QtWidgets.QLabel("Falloff Loops:")
        self.falloffLoops_value = QtWidgets.QSpinBox()
        self.falloffLoops_value.setRange(0, 30)
        self.falloffLoops_value.setSingleStep(1)
        self.falloffLoops_value.setValue(8)

        self.topSkin_check = QtWidgets.QCheckBox(
            'Compute Topological Autoskin')
        self.topSkin_check.setChecked(False)

        # Side
        self.mode_group = QtWidgets.QGroupBox("Symmetry:")
        self.mode_label = QtWidgets.QLabel("Mode:")
        self.mode_comboBox = QtWidgets.QComboBox()
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                           QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.mode_comboBox.sizePolicy().hasHeightForWidth())
        self.mode_comboBox.setSizePolicy(sizePolicy)
        self.mode_comboBox.addItem("On")
        self.mode_comboBox.addItem("Off")

        # Options
        self.options_group = QtWidgets.QGroupBox("Options")

        # default options
        self.browThickness_label = QtWidgets.QLabel("Brow Thickness:")
        self.browThickness_value = QtWidgets.QDoubleSpinBox()
        self.browThickness_value.setRange(0, 10)
        self.browThickness_value.setSingleStep(.01)
        self.browThickness_value.setValue(.03)

        # Side if single
        self.side_label = QtWidgets.QLabel("Side:")
        self.side_comboBox = QtWidgets.QComboBox()
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                           QtWidgets.QSizePolicy.Fixed)
        # sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.side_comboBox.sizePolicy().hasHeightForWidth())
        self.side_comboBox.setSizePolicy(sizePolicy)
        self.side_comboBox.addItem("C")
        self.side_comboBox.addItem("L")
        self.side_comboBox.addItem("R")

        self.side_comboBox.setHidden(True)
        self.side_label.setHidden(True)

        # main divisions
        self.mainDivisions_label = QtWidgets.QLabel("Main Controls:")
        self.mainDivisions_value = QtWidgets.QDoubleSpinBox()
        self.mainDivisions_value.setRange(0, 10)
        self.mainDivisions_value.setSingleStep(1)
        self.mainDivisions_value.setValue(3)
        self.mainDivisions_value.setDecimals(0)
        self.mainDivisions_value.setMinimum(3)

        # secondary divisions
        self.secDivisions_label = QtWidgets.QLabel("Secondary Controls:")
        self.secDivisions_value = QtWidgets.QDoubleSpinBox()
        self.secDivisions_value.setRange(0, 10)
        self.secDivisions_value.setSingleStep(1)
        self.secDivisions_value.setValue(5)
        self.secDivisions_value.setDecimals(0)
        self.secDivisions_value.setMinimum(3)

        # secondary controls ?
        self.secondaryCheck = QtWidgets.QCheckBox('Secondary controls')
        self.secondaryCheck.setChecked(True)

        # Parents
        self.joints_group = QtWidgets.QGroupBox("Parent / Joints")
        self.controls_group = QtWidgets.QGroupBox("Controls")

        # central/main parent
        self.c_browJnt_label = QtWidgets.QLabel("Main/central brow joint:")
        self.c_browJnt_lineEdit = QtWidgets.QLineEdit()
        self.c_browJnt_button = QtWidgets.QPushButton("<<")

        # side joints
        self.l_browJnt_label = QtWidgets.QLabel("Left brow joint:")
        self.l_browJnt_lineEdit = QtWidgets.QLineEdit()
        self.l_browJnt_button = QtWidgets.QPushButton("<<")

        self.r_browJnt_label = QtWidgets.QLabel("Right brow joint:")
        self.r_browJnt_lineEdit = QtWidgets.QLineEdit()
        self.r_browJnt_button = QtWidgets.QPushButton("<<")

        # ctl parents
        self.l_browCtl_label = QtWidgets.QLabel("Main / Left control:")
        self.l_browCtl_lineEdit = QtWidgets.QLineEdit()
        self.l_browCtl_button = QtWidgets.QPushButton("<<")

        self.r_browCtl_label = QtWidgets.QLabel("Right control:")
        self.r_browCtl_lineEdit = QtWidgets.QLineEdit()
        self.r_browCtl_button = QtWidgets.QPushButton("<<")

        # static parent
        self.parent_label = QtWidgets.QLabel("Static Rig Parent:")
        self.parent_lineEdit = QtWidgets.QLineEdit()
        self.parent_button = QtWidgets.QPushButton("<<")

        # Build button
        self.build_button = QtWidgets.QPushButton("Build Brows Rig")
        self.import_button = QtWidgets.QPushButton("Import Config from json")
        self.export_button = QtWidgets.QPushButton("Export Config to json")

    def create_layout(self):

        # Edge Loop Layout
        edgeloop_layout = QtWidgets.QHBoxLayout()
        edgeloop_layout.setContentsMargins(1, 1, 1, 1)
        edgeloop_layout.addWidget(self.edgeloop_label)
        edgeloop_layout.addWidget(self.edgeloop_lineEdit)
        edgeloop_layout.addWidget(self.edgeloop_button)

        # Geometry Input Layout
        geometryInput_layout = QtWidgets.QVBoxLayout()
        geometryInput_layout.setContentsMargins(6, 1, 6, 2)
        geometryInput_layout.addLayout(edgeloop_layout)
        self.geometryInput_group.setLayout(geometryInput_layout)

        # Symmetry mode Layout
        sym_layout = QtWidgets.QHBoxLayout()
        sym_layout.setContentsMargins(1, 1, 1, 1)
        sym_layout.addWidget(self.mode_label)
        sym_layout.addWidget(self.mode_comboBox)

        # Side if single
        side_layout = QtWidgets.QHBoxLayout()
        side_layout.setContentsMargins(1, 1, 1, 1)
        side_layout.addWidget(self.side_label)
        side_layout.addWidget(self.side_comboBox)

        mode_layout = QtWidgets.QVBoxLayout()
        mode_layout.setContentsMargins(6, 4, 6, 4)
        mode_layout.addLayout(sym_layout)
        mode_layout.addLayout(side_layout)
        self.mode_group.setLayout(mode_layout)

        # parents Layout
        # joints
        l_browJnt_layout = QtWidgets.QHBoxLayout()
        l_browJnt_layout.addWidget(self.l_browJnt_label)
        l_browJnt_layout.addWidget(self.l_browJnt_lineEdit)
        l_browJnt_layout.addWidget(self.l_browJnt_button)

        r_browJnt_layout = QtWidgets.QHBoxLayout()
        r_browJnt_layout.addWidget(self.r_browJnt_label)
        r_browJnt_layout.addWidget(self.r_browJnt_lineEdit)
        r_browJnt_layout.addWidget(self.r_browJnt_button)

        c_browJnt_layout = QtWidgets.QHBoxLayout()
        c_browJnt_layout.addWidget(self.c_browJnt_label)
        c_browJnt_layout.addWidget(self.c_browJnt_lineEdit)
        c_browJnt_layout.addWidget(self.c_browJnt_button)

        # controls
        l_browCtl_layout = QtWidgets.QHBoxLayout()
        l_browCtl_layout.addWidget(self.l_browCtl_label)
        l_browCtl_layout.addWidget(self.l_browCtl_lineEdit)
        l_browCtl_layout.addWidget(self.l_browCtl_button)

        r_browCtl_layout = QtWidgets.QHBoxLayout()
        r_browCtl_layout.addWidget(self.r_browCtl_label)
        r_browCtl_layout.addWidget(self.r_browCtl_lineEdit)
        r_browCtl_layout.addWidget(self.r_browCtl_button)

        # static parent
        staticParent_layout = QtWidgets.QHBoxLayout()
        staticParent_layout.addWidget(self.parent_label)
        staticParent_layout.addWidget(self.parent_lineEdit)
        staticParent_layout.addWidget(self.parent_button)

        # joing layout
        parents_layout = QtWidgets.QVBoxLayout()
        parents_layout.setContentsMargins(6, 4, 6, 4)
        parents_layout.addLayout(staticParent_layout)
        parents_layout.addLayout(l_browJnt_layout)
        parents_layout.addLayout(r_browJnt_layout)
        parents_layout.addLayout(c_browJnt_layout)
        self.joints_group.setLayout(parents_layout)

        controls_layout = QtWidgets.QVBoxLayout()
        controls_layout.setContentsMargins(6, 4, 6, 4)
        controls_layout.addLayout(l_browCtl_layout)
        controls_layout.addLayout(r_browCtl_layout)
        self.controls_group.setLayout(controls_layout)

        # Options Layout
        browThickness_layout = QtWidgets.QHBoxLayout()
        browThickness_layout.addWidget(self.browThickness_label)
        browThickness_layout.addWidget(self.browThickness_value)

        secondaryCheck_layout = QtWidgets.QVBoxLayout()
        secondaryCheck_layout.setContentsMargins(6, 4, 6, 4)
        secondaryCheck_layout.addWidget(self.secondaryCheck, alignment=0)

        mainDivisions_layout = QtWidgets.QHBoxLayout()
        mainDivisions_layout.addWidget(self.mainDivisions_label)
        mainDivisions_layout.addWidget(self.mainDivisions_value)

        secDivisions_layout = QtWidgets.QHBoxLayout()
        secDivisions_layout.addWidget(self.secDivisions_label)
        secDivisions_layout.addWidget(self.secDivisions_value)

        options_layout = QtWidgets.QVBoxLayout()
        options_layout.setContentsMargins(6, 1, 6, 2)
        options_layout.addLayout(secondaryCheck_layout)
        options_layout.addLayout(browThickness_layout)
        options_layout.addLayout(mainDivisions_layout)
        options_layout.addLayout(secDivisions_layout)
        self.options_group.setLayout(options_layout)

        # Name prefix
        namePrefix_layout = QtWidgets.QHBoxLayout()
        namePrefix_layout.setContentsMargins(1, 1, 1, 1)
        namePrefix_layout.addWidget(self.prefix_lineEdit)
        self.prefix_group.setLayout(namePrefix_layout)

        # Control Name Extension
        controlExtension_layout = QtWidgets.QHBoxLayout()
        controlExtension_layout.setContentsMargins(1, 1, 1, 1)
        controlExtension_layout.addWidget(self.control_lineEdit)
        self.control_group.setLayout(controlExtension_layout)

        # topological autoskin Layout
        skinLoops_layout = QtWidgets.QGridLayout()
        skinLoops_layout.addWidget(self.rigidLoops_label, 0, 0)
        skinLoops_layout.addWidget(self.falloffLoops_label, 0, 1)
        skinLoops_layout.addWidget(self.rigidLoops_value, 1, 0)
        skinLoops_layout.addWidget(self.falloffLoops_value, 1, 1)

        topoSkin_layout = QtWidgets.QVBoxLayout()
        topoSkin_layout.setContentsMargins(6, 4, 6, 4)
        topoSkin_layout.addWidget(self.topSkin_check, alignment=0)
        topoSkin_layout.addLayout(skinLoops_layout)
        topoSkin_layout.addLayout(parents_layout)
        self.topoSkin_group.setLayout(topoSkin_layout)

        # Main Layout
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.addWidget(self.prefix_group)
        main_layout.addWidget(self.control_group)
        main_layout.addWidget(self.geometryInput_group)
        main_layout.addWidget(self.mode_group)
        main_layout.addWidget(self.options_group)
        main_layout.addWidget(self.joints_group)
        main_layout.addWidget(self.controls_group)
        main_layout.addWidget(self.topoSkin_group)
        main_layout.addWidget(self.build_button)
        main_layout.addWidget(self.import_button)
        main_layout.addWidget(self.export_button)

        self.setLayout(main_layout)

    def create_connections(self):
        self.mode_comboBox.currentTextChanged.connect(self.setSymmetryLayout)
        self.secondaryCheck.stateChanged.connect(self.setSecondaryControls)

        self.edgeloop_button.clicked.connect(partial(self.populate_edgeloop,
                                                     self.edgeloop_lineEdit))

        self.parent_button.clicked.connect(partial(self.populate_element,
                                                   self.parent_lineEdit))

        self.l_browJnt_button.clicked.connect(partial(self.populate_element,
                                                      self.l_browJnt_lineEdit,
                                                      "joint"))

        self.r_browJnt_button.clicked.connect(partial(self.populate_element,
                                                      self.r_browJnt_lineEdit,
                                                      "joint"))

        self.c_browJnt_button.clicked.connect(partial(self.populate_element,
                                                      self.c_browJnt_lineEdit,
                                                      "joint"))

        self.l_browCtl_button.clicked.connect(partial(self.populate_element,
                                                      self.l_browCtl_lineEdit))

        self.r_browCtl_button.clicked.connect(partial(self.populate_element,
                                                      self.r_browCtl_lineEdit))

        self.build_button.clicked.connect(self.build_rig)
        self.import_button.clicked.connect(self.import_settings)
        self.export_button.clicked.connect(self.export_settings)

    def setSymmetryLayout(self, value):
        if value == "Off":
            self.side_comboBox.setHidden(False)
            self.side_label.setHidden(False)

            self.l_browJnt_label.setHidden(True)
            self.l_browJnt_lineEdit.setHidden(True)
            self.l_browJnt_button.setHidden(True)

            self.r_browJnt_label.setHidden(True)
            self.r_browJnt_lineEdit.setHidden(True)
            self.r_browJnt_button.setHidden(True)

            self.r_browCtl_label.setHidden(True)
            self.r_browCtl_lineEdit.setHidden(True)
            self.r_browCtl_button.setHidden(True)
        else:
            self.side_comboBox.setHidden(True)
            self.side_label.setHidden(True)

            self.l_browJnt_label.setHidden(False)
            self.l_browJnt_lineEdit.setHidden(False)
            self.l_browJnt_button.setHidden(False)

            self.r_browJnt_label.setHidden(False)
            self.r_browJnt_lineEdit.setHidden(False)
            self.r_browJnt_button.setHidden(False)

            self.r_browCtl_label.setHidden(False)
            self.r_browCtl_lineEdit.setHidden(False)
            self.r_browCtl_button.setHidden(False)

    def setSecondaryControls(self, value):
        if value == 0:
            self.secDivisions_label.setHidden(True)
            self.secDivisions_value.setHidden(True)
        else:
            self.secDivisions_label.setHidden(False)
            self.secDivisions_value.setHidden(False)
    #SLOTS ##########################################################

    def populate_element(self, lEdit, oType="transform"):
        if oType == "joint":
            oTypeInst = pm.nodetypes.Joint
        elif oType == "vertex":
            oTypeInst = pm.MeshVertex
        else:
            oTypeInst = pm.nodetypes.Transform

        oSel = pm.selected()
        if oSel:
            if isinstance(oSel[0], oTypeInst):
                lEdit.setText(oSel[0].name())
            else:
                pm.displayWarning(
                    "The selected element is not a valid %s" % oType)
        else:
            pm.displayWarning("Please select first one %s." % oType)

    def populate_edgeloop(self, lineEdit):
        lineEdit.setText(lib.get_edge_loop_from_selection())

    def build_rig(self):
        rig(**lib.get_settings_from_widget(self))

    def export_settings(self):
        data_string = json.dumps(
            lib.get_settings_from_widget(self), indent=4, sort_keys=True
        )

        file_path = lib.get_file_path(self.filter, "save")
        if not file_path:
            return

        with open(file_path, "w") as f:
            f.write(data_string)

    def import_settings(self):
        file_path = lib.get_file_path(self.filter, "open")
        if not file_path:
            return

        lib.import_settings_from_file(file_path, self)


# Build from json file.
def rig_from_file(path):
    rig(**json.load(open(path)))


def show(*args):
    gqt.showDialog(ui)


if __name__ == "__main__":
    show()
