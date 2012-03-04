#  ***** GPL LICENSE BLOCK *****
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#  All rights reserved.
#  ***** GPL LICENSE BLOCK *****


# Release Log (more info in __init__.py for io_export_maxwell)
# ============================================================
# 0.5 First Public release 
# ------------
# 0.4 Private release 
# * cleaning
# * update for Blender 2.62 matrix access
# ------------
# 0.3 Private release 
# * added scene to export interface
# * visibility object check
# ------------
# 0.2 Private release 
# * update for Blender 2.61 camera settings
# ------------
# 0.1 Private release 
# * initial release
# ------------



if ("bpy" in locals()):
    import imp
    if ("pymaxwell" in locals()):
        imp.reload(pymaxwell)
    if ("logutil" in locals()):
        imp.reload(logutil)

import os
import time
import shutil

import bpy
import math
from math import *
import mathutils
import bpy_extras.io_utils




# ===========================================================
# === Util functions ========================================
# ===========================================================


# -----------------------------------------------------------
def name_compat(name):
    if (name is None):
        return 'None'
    else:
        return name.replace(' ', '_')
# end def name_compat


# -----------------------------------------------------------
def appendUnique(ll, name):
    '''
      generates a unique string "name" 
      among the ones already contained in keys of dict "ll"
    '''
    if ((ll is None) or 
       (type(ll) != type ({})) or
       (name is None) or
       (name == "") or  
       (type(name) != type (""))):
        return Name
    postfixNum = 0
    testName = name
    while testName in ll:
        postfixNum = postfixNum +1
        testName = name + '_{:0>3}'.format(postfixNum)
    return testName
# end def appendUnique


# -----------------------------------------------------------
def isRenderable(scene, ob):
    return (ob.is_visible(scene) and not ob.hide_render)
# end def appendUnique


# -----------------------------------------------------------
def renderableObjects(scene):
    return [ob for ob in scene.objects if isRenderable(scene, ob)]
# end def appendUnique

# -----------------------------------------------------------
def scName(p):
    '''
       Paranoid sanity check on names
       p is a blender object with a "name" attribute - no checks on this!
       true = name not valid
       false = name valid
    '''
    try:
       a = repr(p.name)
       f = False
    except:
       f = True
    return f
# end def sanityCheck


# ===========================================================
# === Exporter Class ========================================
# ===========================================================
class export:
    
    # -----------------------------------------------------------
    def __init__(self, 
                 operator, 
                 context, 
                 scene=None,
                 path_mode='AUTO',
                 use_selection=True,
                 global_matrix=None,
                 global_scale=1.0,
                 filepath="",
                 use_uvs=True,
                 use_apply_modifiers=True,
                 use_apply_xform=False,
                 use_materials=True):
        
        #initializing logging facility
        from . import logutil
        #textname = "mxs_log"
        #uncomment the following line to disable facility
        textname = None
        self.tobj=logutil.dotext(textname)
        self.tobj.tofile(filepath + ".log")
        self.tobj.pprint("MXS Export 0.4",)
        self.tobj.pprint("Blender: ", bpy.app.version_string)
        self.tobj.pprint("MXS Export path: ", filepath)
        
        tt = self.tobj
        tt.pprint(context)
        tt.pprint(scene)
        tt.pprint(filepath)
        tt.pprint(path_mode)
        tt.pprint(use_selection)
        tt.pprint(global_matrix)
        tt.pprint(global_scale)
        tt.pprint(filepath)
        tt.pprint(use_uvs)
        tt.pprint(use_apply_modifiers)
        tt.pprint(use_apply_xform)
        tt.pprint(use_materials)
        
        self.OPERATOR=operator
        self.CONTEXT=context
        self.SCENE=scene
        if (scene is None):
            self.SCENE=self.CONTEXT.scene
        self.PATH_MODE=path_mode
        self.SEL_ONLY=use_selection
        if (global_matrix is None):
            self.GLOBAL_MATRIX = mathutils.Matrix()
        else:
            self.GLOBAL_MATRIX=global_matrix
        self.GLOBAL_SCALE=global_scale
        self.FILEPATH=filepath
        self.EXPORT_UV=use_uvs
        self.APPLY_XFORM=use_apply_xform
        self.APPLY_MODIFIERS=use_apply_modifiers
        self.EXPORT_MTL=use_materials
        self.MAXWELL2_ROOT=None
        if ('MAXWELL2_ROOT' in os.environ):
            self.MAXWELL2_ROOT=os.environ['MAXWELL2_ROOT']
        self.tobj.pprint('MAXWELL2_ROOT is ', self.MAXWELL2_ROOT)
        
        self.MXMCache={} # filename -> complete filepath
        if use_materials:
            self.fillMXMCache()
        
        from . import pymaxwell #import once 
        self.pm = pymaxwell
        
    #end def __init__
    

    # -------------------------------------------------------
    def scan4Mat(self, dir):
        """
            Recursively scan for a directory getting all the materials
   
            @type  dir: string
            @param dir: full path to directory to be scan
            @return: dictionary with an entry for each material found in the 
                     specified directory (and below ...){filename -> full path}
                     or an empty dictionary
        """
    
        filedict ={}
        for root, dirs, files in os.walk(dir):
            tmpfiles = ( (name, os.path.join(root, name)) for name in files if (name[-4:].lower()==".mxm") )
            for n, p in tmpfiles:
               filedict[n] = p
        return filedict
    # end scan4Mat -------------------------------------------

    # -----------------------------------------------------------
    def fillMXMCache(self):
        """
            Pre-Filling of the cache materials with all materials found in both:
            - the current file path (and subdirs)
            - the current Maxwell2 installation path (and subdirs)
            also checks if the two above are not one subdir of the other, avoiding double checks
        """

        self.tobj.pprint("Caching materials ...")
        curd = os.path.dirname(bpy.data.filepath)

        searchdirs = [curd]
        if self.MAXWELL2_ROOT:
           pp = os.path.commonprefix([curd, self.MAXWELL2_ROOT])
           # if (pp == curd): already ok
           if (pp == self.MAXWELL2_ROOT):
               searchdirs = [self.MAXWELL2_ROOT]
           else:
               searchdirs = [self.MAXWELL2_ROOT, curd]

        for dd in searchdirs:
            self.tobj.pprint("... caching: ", dd)
            self.MXMCache.update(self.scan4Mat(dd))

        self.tobj.pprint(self.MXMCache)
        
    # end fillMXMCache -------------------------------------------


    # -----------------------------------------------------------
    def writeFile(self,
                   filepath,
                   objects,
                   scene):

        # -----------------------------------------------------------
        def setObjParameters(mxOb, obMat, blOb):
            '''
                set position - rotatation - scale for the new maxwell object/instance
                need to pass the transformation Matrix cause duplis has different matrix than base object
            '''

            self.tobj.pprint ("*** matrix: ")
            self.tobj.pprint (obMat)

            #mmat = obMat.copy()
            #negative scale trick
            #scmat = correctionMatrix(blOb))
            # mmat = obMat * scmat

            # Base setup
            newBase = self.pm.Cbase()
            mxXB = self.pm.Cvector()
            mxYB = self.pm.Cvector()
            mxZB = self.pm.Cvector()
            mxOB = self.pm.Cvector()

            #mxXB.assign(mmat[0][0], mmat[0][1], mmat[0][2])
            #mxYB.assign(mmat[1][0], mmat[1][1], mmat[1][2])
            #mxZB.assign(mmat[2][0], mmat[2][1], mmat[2][2])
            #mxOB.assign(obMat[3][0], obMat[3][1], obMat[3][2])

            mxXB.assign(obMat[0][0], obMat[1][0], obMat[2][0])
            mxYB.assign(obMat[0][1], obMat[1][1], obMat[2][1])
            mxZB.assign(obMat[0][2], obMat[1][2], obMat[2][2])
            mxOB.assign(obMat[0][3], obMat[1][3], obMat[2][3])

            newBase.origin = mxOB
            newBase.xAxis = mxXB
            newBase.yAxis = mxYB
            newBase.zAxis = mxZB

            # Pivot setup
            newPivot = self.pm.Cbase()
            mxXP = self.pm.Cvector()
            mxYP = self.pm.Cvector()
            mxZP = self.pm.Cvector()
            mxOP = self.pm.Cvector()

            mxXP.assign(1.0, 0.0, 0.0)
            mxYP.assign(0.0, 1.0, 0.0)
            mxZP.assign(0.0, 0.0, 1.0)
            mxOP.assign(0.0, 0.0, 0.0)

            newPivot.origin = mxOP
            newPivot.xAxis = mxXP
            newPivot.yAxis = mxYP
            newPivot.zAxis = mxZP
            
            # assign
            mxOb.setBaseAndPivot(newBase,newPivot)
            
            
        #end def setObjParameters -----------------------------------
        

        # -----------------------------------------------------------
        def correctionMatrix(blOb):
            '''
                set position - rotatation - scale for the new maxwell object/instance
                need to pass the transformation Matrix cause duplis has different matrix than base object
                currently not used - left in place for this release
            '''

            scmat = mathutils.Matrix()
            scmat.identity()

            if (blOb is None):
                return scmat

            #negative scale trick - part 1
            if (blOb.scale[0]<0.0):
               scmat[0][0] = -1.0
            if (blOb.scale[1]<0.0):
               scmat[1][1] = -1.0
            if (blOb.scale[2]<0.0):
               scmat[2][2] = -1.0
            return scmat
        #end def correctionMatrix -----------------------------------



        # -----------------------------------------------------------
        def writeMaterial(mxPointer, mat, mtl_dict):
            """
                Export a material
                Do not export material parameters, but setsa a reference to an external material already present on file system
       
                @type  mxPointer: CMaxwell
                @param mxPointer: reference to Maxwell class for materials creation
                @type  mat: blender material
                @param mat: material to be exported
                @type  mtl_dict: dict {blender material -> maxwell material)
                @param mtl_dict: dictionalry of already exported materials
                @return: the Maxwell material correspondent to material (or None if something went wrong, that is, there are no maxwell corresponding materials ...) 
            """

            if not(mat) or not(mxPointer) or (mtl_dict is None):
                return None

            if scName(mat):
               self.tobj.pprint ("**** A MATERIAL NAME HAS BEEN REQUESTED THAT CANNOT BE HANDLED BY THE EXPORTER AND WILL BE IGNORED")
               return None
               
            mName=mat.name
            self.tobj.pprint ("Material requested: ", mName)
            if mName[-4:].lower()!=".mxm":
                self.tobj.pprint ("! not a maxwell material, skipping")
                return None

            if mName in mtl_dict:
                self.tobj.pprint ("already exported - giving reference")
                return mtl_dict[mName]

            mPath = mat.get("mxm-path", None)
            tmpDict ={}
            if mPath: #ok, search the material into the file system
                mPath = bpy.path.abspath(mPath)
                self.tobj.pprint ("specific search in: ", mPath)
                tmpDict = self.scan4Mat(mPath)

            mFullName = None
            if mName in tmpDict:
                mFullName = tmpDict[mName]
            elif mName in self.MXMCache:
                mFullName = self.MXMCache[mName]

            if mFullName:
                self.tobj.pprint ("not yet exported - creating")
                tmpMat = Mx.readMaterial(mFullName)
                MxMat = Mx.addMaterial(tmpMat)
                mtl_dict[mName] = MxMat
                return MxMat

            self.tobj.pprint ("! no reference found in search directories")
            return None

        #end def writeMaterial --------------------------------------

        # -----------------------------------------------------------
        def writeEmpty(ob, obMat, meshName, exportedMeshes):
            """
                Write a NULL object
       
                @type  ob: blender object
                @param ob: object that is exported as NULL = empty or no faces (to_mesh methods not applicable)
                @type obMat: matrix
                @param obMat: matrix for object transformations
                @type  exportedMeshes: dict mapping {meshname -> mxObject}
                @param exportedMeshes: collect meshes created in Maxwell
                @rtype:   Maxwell Object
                @return:  the Maxwell Object corresponding to the object passed as parameter
            """
            if (scName(ob)):
                self.tobj.pprint ("**** AN EMPTY OBJECT NAME HAS BEEN REQUESTED THAT CANNOT BE HANDLED BY THE EXPORTER AND WILL BE IGNORED")
                return None
            
            MxObject = Mx.createMesh(ob.name,
                                     0,      #Number of vertices
                                     0,      #Number of normals
                                     0,      #Number of triangles
                                     1)      #Position per vertexes

            setObjParameters(MxObject, obMat, ob)
            exportedMeshes[meshName] = MxObject
      
            return MxObject
        #end def writeEmpty -----------------------------------------
 
        # -----------------------------------------------------------
        def writeCamera(ob, obMat, obName, rSet, active):
            """
                Write a CAMERA object
       
                @type  ob: blender object
                @param ob: camera object to be exported
                @type obMat: matrix
                @param obMat: matrix for object transformations
                @type  obName: string
                @param obName: name of the camera object
                @type  rSet: blender render settings
                @param rSet: some parameters gathered from here
                @type  active: bool
                @param active: set this camera as the active one for rendering.
                @rtype:   Maxwell Camera
                @return:  the Maxwell Camera corresponding to the object passed as parameter
            """
            if not (ob.data): #paranoid
               return None

            #if not (active): #just the active one - to export all just remove these two lines 
            #   return None
    
            if not (ob.data.type == 'PERSP'): 
               self.tobj.pprint("*** ACTIVE CAMERA NOT EXPORTED - CANNOT BE ORTHO - MUST BE PERSPECTIVE")
               return None
            projectionType = 0 #perspective
    
            nSteps = 1;
            shutter = 1 / ob.data.get("shutter", 250.0) #1/s
            iso = ob.data.get("iso", 100.0) 
            diaphragmType = ob.data.get("diaphragm", "C") # C = circular, P = polygonal
            if diaphragmType[0] == "P":
                diaphragmType = "POLYGONAL"
            else:
                diaphragmType = "CIRCULAR"
            diaphragmAngle = ob.data.get("dia-angle", 60) # Poly only in degrees
            diaphragmBlades = ob.data.get("dia-bladenum", 6) # Poly only
            fps = rSet.fps
            xRes = int(rSet.resolution_x * rSet.resolution_percentage / 100.0)
            yRes = int(rSet.resolution_y * rSet.resolution_percentage / 100.0)
            pixelAspect = rSet.pixel_aspect_x/rSet.pixel_aspect_y

            # width and height must have the same proportion as resX and resY
            # resX and resY drives! then depending on blender sensor_fit given one dimension 
            # the other is calculated
            sFit = ob.data.sensor_fit
            filmHeight = ob.data.sensor_height / 1000.0 # mm, converted in meters
            filmWidth = ob.data.sensor_width / 1000.0 # mm, converted in meters

            if (ob.data.sensor_fit=='AUTO'):
                if (xRes>yRes): #priority is horizontal
                    filmWidth = ob.data.sensor_width / 1000.0 # mm, converted in meters
                    sFit = 'HORIZONTAL'
                else: #priority is vertical
                    filmHeight = ob.data.sensor_width / 1000.0 # omg. width in this case should be named "size". mm, converted in meters
                    sFit = 'VERTICAL'

            if (sFit=='VERTICAL'):
                filmWidth = (filmHeight * xRes) / yRes  #height rulez => width is calculated 
            else: # HORIZONTAL: just 2 choices here
                filmHeight = (filmWidth * yRes) / xRes  #width rulez
           
            self.tobj.pprint ("*** sensor fit: ", ob.data.sensor_fit)
            self.tobj.pprint ("*** computed fit: ", sFit)
            self.tobj.pprint ("*** filmWidth: ", filmWidth)
            self.tobj.pprint ("*** filmHeight: ", filmHeight)

            MxCamera = Mx.addCamera( obName,
                                     nSteps, 
                                     shutter, 
                                     filmWidth, 
                                     filmHeight, 
                                     iso, 
                                     diaphragmType,
                                     diaphragmAngle, 
                                     diaphragmBlades, 
                                     fps, 
                                     xRes, 
                                     yRes, 
                                     pixelAspect, 
                                     projectionType)

            origin = self.pm.Cvector()
            focalPoint = self.pm.Cvector()
            up = self.pm.Cvector()

            blPos = ob.matrix_world.to_translation() #camera cannot be part of the hierarchy, so take world matrix
            self.tobj.pprint ("*** camera origin: ", tuple(blPos))
            origin.assign(blPos[0], blPos[1], blPos[2])

            if ob.data.dof_object:
                self.tobj.pprint ("*** object DOF")
                tgPos = ob.data.dof_object.matrix_world.to_translation()
                dofDist = (blPos - tgPos).length # dof is the distance between 2 objects
            else:
                self.tobj.pprint ("*** DOF dist")
                dofDist = ob.data.dof_distance
                if (dofDist==0.0):
                   dofDist = 1.0
                
            self.tobj.pprint ("*** distance: ", dofDist)
            # the point in space in focus that the camera is looking at is the following
            # blender camera looks at local -z direction
            dofVector = ob.matrix_world * mathutils.Vector((0.0, 0.0, -dofDist))
            self.tobj.pprint ("*** camera focal point: ", tuple(dofVector))
            focalPoint.assign(dofVector[0], dofVector[1], dofVector[2])

            upVector = ob.matrix_world * mathutils.Vector((0.0, 1.0, 0.0)) - blPos
            self.tobj.pprint ("*** up vector: ", tuple(upVector))
            up.assign(upVector[0], upVector[1], upVector[2])

            # get some more accuracy in calculating the focal length of the camera
            # details in http://home.metrocast.net/~chipartist/BlensesSite/index.html
            # takes blender camera FOV and calculates maxwell camera focal
            # finite DoF ---------------------------
            #self.tobj.pprint ("*** angle: %s" % str(ob.data.angle * 180 / math.pi))
            #mag =  math.hypot(filmWidth, filmHeight) / (2 * dofDist * math.tan(ob.data.angle / 2)) 
            #focalLength = (mag * dofDist) / (mag + 1)
            # focus to infinite ---------------------------
            self.tobj.pprint ("*** angle: ", math.degrees(ob.data.angle))
            
            #focalLength =  max(filmWidth, filmHeight) / (2 * math.tan(ob.data.angle / 2)) 
            focalLength = ob.data.lens / 1000.0 # mm, converted in meters
            
            self.tobj.pprint ("*** computed focal-length: ", focalLength)
            self.tobj.pprint ("*** blender focal-length: ", ob.data.lens)

            fStop = ob.data.get("f-stop", 8)

            MxCamera.setStep( 0, # step
                              origin,
                              focalPoint, 
                              up,
                              focalLength, 
                              fStop,
                              1 ) # True

            MxCamera.setCutPlanes(ob.data.clip_start, 
                                  ob.data.clip_end, 
                                  1) #enabled

            MxCamera.setShiftLens(ob.data.shift_x * 10.0, # bl=[-10 to 10]; mw=[-100 to 100]
                                  ob.data.shift_y * 10.0)

            if active:
                MxCamera.setActive()

            return MxCamera
        #end def writeCamera -----------------------------------------


        # -----------------------------------------------------------
        def writeObject(scene, obMain, exportedMeshes, exportedMaterials, useWorldMatrix = False):
            """
                Recursively writes the sub-hyerarchy that has object as root (+ the object itself)
       
                @type  scene: blender scene
                @param scene: current scene
                @type  obMain: blender object
                @param obMain: object root of sub-hyerarchy to be exported
                @type  exportedMeshes: dict mapping {meshname -> mxObject}
                @param exportedMeshes: collect meshes created in Maxwell
                @type  exportedMaterials: dict mapping {materialname -> mxMaterial}
                @param exportedMaterials: collect materials created in Maxwell
                @type  useWorldMatrix: boolean
                @param useWorldMatrix: use world matrix for orientation (to be used for root objects)
                @rtype:   Maxwell Object
                @return:  the Maxwell Object corresponding to the object passed as parameter
            """
    
            pm = self.pm    #lazy programmer
            tt = self.tobj
            
            if (scName(obMain)):
                tt.pprint ("**** AN OBJECT NAME HAS BEEN REQUESTED THAT CANNOT BE HANDLED BY THE EXPORTER")
                tt.pprint ("     THIS OBJECT AND ALL ITS CHILDREN WILL BE IGNORED")
                return None

            #XXX correct negative scale trick
            #BEWARE we are going to modify the original file!!!!
            #negative scale trick - part 1
            if (self.APPLY_XFORM and ((obMain.scale[0]<0.0) or (obMain.scale[1]<0.0) or (obMain.scale[2]<0.0))):
                tt.pprint("*** for sub-h rooted on ", obMain.name, " applied scale transformations")
                bpy.ops.object.select_name(name = obMain.name, extend = False)
                bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            
            # ATTENTION: Base dupli objects ARE exported. 

            MxChildrenList = (writeObject(scene, child, exportedMeshes, exportedMaterials, False) 
                              for child in obMain.children 
                              if obMain.children)
            MxChildrenList = [x for x in MxChildrenList if x] #remove the eventual None objects generated by writeObject
            numChildren = len(MxChildrenList)

            tt.pprint ("\nThis is ", obMain.name, " object that has the following children")

            # ATTENTION: Dupliverting object IS exported. 
            # eventually add a flag to check for exporting this one too when exporting dupli children
            if (useWorldMatrix):
                obs = [(obMain, obMain.matrix_world, obMain.name, False)]
            else:
                obs = [(obMain, obMain.matrix_local, obMain.name, False)]
           # tuple:
            # 0. blender object
            # 1. matrix to be used (if dupli is not the same as object above)
            # 2. name for the maxwell object (if None use the blender object name)
            # 3. True = this obj is dupli
            if (obMain.type == 'MESH') and (obMain.dupli_type in {'VERTS', 'FACES'}):
                tt.pprint("*** creating dupli_list on ", obMain.name)
                obMain.dupli_list_create(scene)                          
                obs.extend([(dob.object, 
                             dob.matrix, 
                             dob.object.name + '_dupli_{:0>3}'.format(index), 
                             True)  #is a dupli
                             for index, dob in enumerate(obMain.dupli_list)
                             if not(scName(dob))])
                tt.pprint("*** ", obMain.name, " has ", len(obs)-1," dupli children")
   

            MxObject = None #if current object is not exported then supply something to return
            for ob, obMat, obName, isDupli in obs:
                tt.pprint ("*** Creating object: ", obName)

                if ob.type == 'CAMERA':
                    writeCamera(ob, obMat, obName, scene.render, (ob == scene.camera))
                    # continue on and if camera has childrens export an empty to parent them
                generateNew = True

                if ob.data: #is not an empty 
                    meshName = ob.type[0:3] + ob.data.name
                    tt.pprint ("*** that has data name ", meshName)
                    if isDupli:     #if dupli surely is an instance
                        generateNew = False
                    elif (ob.is_modified(scene, 'RENDER') and not(isDupli)):
                        meshName = appendUnique(exportedMeshes, meshName + "_mod")
                        #generateNew = True redundant
                    elif ((meshName in exportedMeshes) and (numChildren==0)): #is a dupli without children
                        generateNew = False
                elif isDupli: #is an empty and a dupli 
                    tt.pprint ("*** skip empty duplis")
                    continue
                else: #is an empty but not a dupli
                    meshName = appendUnique(exportedMeshes, ob.type[0:3] + ob.name)
             
                tt.pprint ("*** Data name: ", meshName,";  GenerateNew: ", generateNew)
    

                if generateNew:
                    #Generate a brand new object
                    tt.pprint ("*** Generating new object ", obName)

                    try:
                        me = ob.to_mesh(scene, self.APPLY_MODIFIERS, 'RENDER')
                    except RuntimeError:
                        me = None
    
                    if (me is None):
                        tt.pprint ("*** Mesh Not exported")
                        if numChildren:
                            tt.pprint("*** but has children, trying with an empty")
                            MxObject = writeEmpty(ob, obMat, meshName, exportedMeshes)
                        continue 
    
                    me_verts = me.vertices[:]
                    tt.pprint ("== found ", len(me.vertices)," vertices")
    
                    tris = [f for f in me.faces if len(f.vertices) == 3]
                    quads = [f for f in me.faces if len(f.vertices) == 4]
                    n_tris = len(tris)
                    n_quads = len(quads)
                    tt.pprint ("== found ", n_tris," tris")
                    tt.pprint ("== found ", n_quads," quads")
                    #tt.pprint (face_index_pairs)
    
                    if (n_tris + n_quads) == 0:  # Make sure there is something to write
                        tt.pprint ("== mesh has no faces, skipping")
                        bpy.data.meshes.remove(me)  # clean up
                        if numChildren:
                            tt.pprint("*** but has children, trying with an empty")
                            MxObject = writeEmpty(ob, obMat, meshName, exportedMeshes) 
                        continue
    
                    # Make our own list so it can be sorted to reduce context switching
                    face_index_pairs = [(face, index) for index, face in enumerate(me.faces)]
    
                    MxObject = Mx.createMesh(obName,
                                             len(me_verts),      #Number of vertices
                                             len(me_verts),      #Number of normals
                                             n_tris + 2*n_quads, #Number of triangles
                                             1)                  #Position per vertexes
    
                    # export all the materials list for this object
                    fwdTriangleGroups = [] # maxwell object material slot = maxwell triangle group -> maxwell material 
                    if self.EXPORT_MTL:
                        for mSlot in ob.material_slots:
                            fwdTriangleGroups.append(writeMaterial(Mx, mSlot.material, exportedMaterials))
                    fwdTriangleGroups = [x for x in fwdTriangleGroups if not(x is None)]
                    numMaterials = len(fwdTriangleGroups)
                    # assign default object
                    if ob.active_material and (ob.active_material.name in exportedMaterials) and (numMaterials == 1):
                         MxObject.setMaterial(exportedMaterials[ob.active_material.name])
                    
                    setObjParameters(MxObject, obMat, ob)
                    exportedMeshes[meshName] = MxObject
                    tt.pprint("Now esported meshes:")
                    tt.pprint(exportedMeshes)
        
                    me.calc_normals()
        
                    for texidx, uvTextures in enumerate(me.uv_textures):
                        tt.pprint("*** found texture layer ", uvTextures.name)
                        tt.pprint("****** mapped on Mx channel ", texidx)
                        MxObject.addChannelUVW(texidx)

                    # VERTEXES ===========================================================================
                    for vidx, v in enumerate(me_verts):
                        #tt.pprint ("=== vertex %d" % vidx)
                        #tt.pprint ("=== coords %s" % str(tuple(v.co)))
                        #tt.pprint ("=== normals %s" % str(tuple(v.normal)))
                        MxVertex = pm.Cvector()                                                 
                        MxVertex.assign(v.co.x, v.co.y, v.co.z)
                        MxObject.setVertex(vidx,                   #Index of vertex
                                           0,                      #Index of position for vertex <Idx>
                                           MxVertex)               #Vertex
                        #tt.pprint ("== read %s" % str(MxObject.getVertex(vidx, 0)))
                        MxNormal = pm.Cvector()
                        MxNormal.assign(v.normal.x, v.normal.y, v.normal.z)
                        MxObject.setNormal(vidx,                   #Index of normal (same order as vertex)
                                           0,                      #Index of position for vertex <Idx>
                                           MxNormal)               #Normal
                        #vertexGroups[vidx] = set() #XXX initialize set 
                        #per ogni gruppo vg di vidx
                        #    vertexGroups[vidx].add(idgruppo)

                    # FACES + NORMALS + UVS ===========================================================================
                    tidx = 0
                    for f, f_index in face_index_pairs:
                        if len(f.vertices)<=2:                     #ehm, is this a single edge?
                            tt.pprint ("=== skipped single edge face ", f_index)
                            continue
                        #tt.pprint ("=== from face %d - tri %d" % (f_index,tidx))
                        #tt.pprint ("=== vertices %d, %d, %d" % (f.vertices[0], f.vertices[1], f.vertices[2]))
                        MxObject.setTriangle(tidx,                 #Index of triangle
                                             f.vertices[0],        #Index of vertices
                                             f.vertices[1],
                                             f.vertices[2],
                                             f.vertices[0],        #Index of normals
                                             f.vertices[1],
                                             f.vertices[2])
                        if numMaterials: #if 0 then just 1 mat, ease things
                            MxObject.setTriangleGroup(tidx, f.material_index)
                        
                        for texidx, uvTexture in enumerate(me.uv_textures): # have a run on tex layers
                            uv = uvTexture.data[f_index].uv
                            MxObject.setTriangleUVW(tidx, texidx, 
                                                    uv[0][0], 1 - uv[0][1], 0.0,    # also -uv[vert][u/v] works, but for tiled texture only 
                                                    uv[1][0], 1 - uv[1][1], 0.0,
                                                    uv[2][0], 1 - uv[2][1], 0.0
                                                    )

                        tidx=tidx+1
                        if len(f.vertices)==4:                     #same quad but this is another tris ...
                            #tt.pprint ("=== from quad face %d - second tri %d" % (f_index, tidx))
                            #tt.pprint ("=== vertices %d, %d, %d" % (f.vertices[0], f.vertices[2], f.vertices[3]))
                            MxObject.setTriangle(tidx,                 #Index of triangle
                                                 f.vertices[0],        #Index of vertices
                                                 f.vertices[2],
                                                 f.vertices[3],
                                                 f.vertices[0],        #Index of normal
                                                 f.vertices[2],
                                                 f.vertices[3])
                            if numMaterials: #if 0 then just 1 mat, ease things
                                MxObject.setTriangleGroup(tidx, f.material_index)

                            for texidx, uvTexture in enumerate(me.uv_textures): # have a run on tex layers
                                uv = uvTexture.data[f_index].uv
                                MxObject.setTriangleUVW(tidx, texidx, 
                                                        uv[0][0], 1 - uv[0][1], 0.0,
                                                        uv[2][0], 1 - uv[2][1], 0.0,
                                                        uv[3][0], 1 - uv[3][1], 0.0
                                                        )
                            tidx=tidx+1

                    if numMaterials:
                        for groupIndex in range(len(fwdTriangleGroups)):
                             MxObject.setGroupMaterial(groupIndex, fwdTriangleGroups[groupIndex])
                    # clean up
                    bpy.data.meshes.remove(me)
    
                else: #!generateNew
                    MxBaseObject = exportedMeshes[meshName]  #base object is the one corresponding to original mesh
                    #MxBaseObject = exportedMeshes[ob.data.name]  #base object is the one corresponding to original mesh
                    tt.pprint ("\n*** Generating new Instance ", obName)
                    tt.pprint ("*** Linked to ", MxBaseObject.getName())
    
                    MxTempObject = Mx.createInstancement(obName,     #Always name instanced object after modified mesh name
                                                         MxBaseObject)

                    if isDupli:
                        tt.pprint("*** adding this dupli to children list")
                        #but this will have no effect (by now?) cause maxwell instances do not support parenting
                        MxChildrenList.append(MxTempObject)
                        # for duplis matrix is already a world matrix
                        setObjParameters(MxTempObject, obMat, ob)
                    else:
                        MxObject = MxTempObject
                        # parenting is not supported, so cannot get transformation matrix from the parent
                        # instead of local_matrix, get the world one
                        setObjParameters(MxTempObject, ob.matrix_world, ob)

                    #XXX code duplicated from the above.
                    #see if works then optimize
                    # export all the materials list for this object
                    if self.EXPORT_MTL:
                        for mSlot in ob.material_slots:
                            MxMaterial = writeMaterial(Mx, mSlot.material, exportedMaterials)
                    # assign default object
                    if ob.active_material and (ob.active_material.name in exportedMaterials) and (numMaterials == 1):
                         MxObject.setMaterial(exportedMaterials[ob.active_material.name])
                    

            if obMain.dupli_type != 'NONE':
                obMain.dupli_list_clear()
    
            #Set Parenthood
            for MxO in MxChildrenList:
                if MxObject: #there is something to parent?
                    #map through lambda does not work :o) map(lambda x: x.setParent(MxObject), MxChildrenList)
                    MxO.setParent(MxObject)

            return MxObject
            
        #end def writeObject ----------------------------------------


        
        pm = self.pm    #lazy programmer
        tt = self.tobj
           
        #Create Maxwell instance
        Mx = pm.Cmaxwell(pm.mwcallback)
        Mx.setInputDataType("ZXY")
        #the setInputDataType pre-sets some scale/rotation to be taken into account when setting up position and rotation
        Mx.setSinglePrecisionOfGeometry()
    


        time1 = time.clock()

        # export ambient data
        # by now constant sky only
        # XXX map luminance and midpoint to blender properties, not custom ones
        wld = scene.world
        if wld:
            luminance = wld.get("luminance", 35000.0)
            midPoint = wld.get("mid-point", 60.0)
            colHorizon = pm.Crgb()
            colHorizon.assign(wld.horizon_color[0], wld.horizon_color[1], wld.horizon_color[2])
            colZenith = colHorizon
            if wld.use_sky_blend:
                colZenith = pm.Crgb()
                colZenith.assign(wld.zenith_color[0], wld.zenith_color[1], wld.zenith_color[2])
            Mx.setActiveSky('CONSTANT')
            Mx.setSkyConstant(luminance, #luminance = intensity in cd/sqm
                              colHorizon,
                              colZenith,
                              midPoint)    #controlPoint = MidPoint
  
        #collect exported objects
        exportedMeshes = {} # {meshname -> mxObject)}
        exportedMaterials = {} # {materialname -> mxMaterial)}

        # export all the sub-hyerarchies
        for obMain in objects:
            writeObject(scene, obMain, exportedMeshes, exportedMaterials, True)
    
        Mx.writeMXS(filepath)
        tt.pprint ("Written: ", filepath)
    
        # Now we have all our materials, save them
        if self.EXPORT_MTL:
            #write_mtl
            pass;
    
        # copy all collected files.
        #bpy_extras.io_utils.path_reference_copy(copy_set)
    
        tt.pprint("MXS Export time: %.2f" % (time.clock() - time1))
        tt.closefile()
    # end def write_file



    
    # -----------------------------------------------------------
    def save(self):
    
        base_name, ext = os.path.splitext(self.FILEPATH)
        context_name = [base_name, '', '', ext]  # Base name, frame number, extension
    
    
        # Exit edit mode before exporting, so current object states are exported properly.
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode='OBJECT')
    
        scene = self.SCENE
        orig_frame = scene.frame_current

        # Export an animation?
        #if EXPORT_ANIMATION:
        #    scene_frames = range(scene.frame_start, scene.frame_end + 1)  # Up to and including the end frame.
        #else:
        #    scene_frames = [orig_frame]  # Dont export an animation.

        scene_frames = [orig_frame]
        
        # Loop through all frames in the scene and export.
        for frame in scene_frames:
            #if EXPORT_ANIMATION:  # Add frame to the filepath.
            #    context_name[2] = '_%.6d' % frame

            scene.frame_set(frame, 0.0)
            # objects generated recursively following objects hyerarchy
            if self.SEL_ONLY:
                # so start from the roots selecting:
                # 1. the ones that have no parent
                # 2. the ones selected, with parent not selected
                objects = self.CONTEXT.selected_objects
                objects = filter(lambda x: (x.parent is None) or not(x.parent in self.CONTEXT.selected_objects), objects)
            else:
                #here really more simple - root renderable objects
                objects = filter(lambda x: (x.parent is None), renderableObjects(scene))

            full_path = ''.join(context_name)

            self.writeFile(full_path,
                            objects,
                            scene)

        scene.frame_set(orig_frame, 0.0)
    
        return {'FINISHED'}
    # end def save ----------------------------------------------
    '''
    Currently the exporter lacks these features:
    * "real" materials export
    * particles
    '''

# end class export ------------------------------------------
