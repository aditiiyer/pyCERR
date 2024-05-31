import json

import numpy as np

import cerr.contour.rasterseg as rs
from cerr import plan_container as pc
from cerr.radiomics import textureFilters
from cerr.radiomics.preprocess import preProcessForRadiomics
from cerr.utils.mask import compute_boundingbox

def loadSettingsFromFile(settingsFile, scanNum=None, planC=None):
    """ Load filter parameters from user-input JSON file"""

    # Read settings
    with open(settingsFile) as json_file:
        paramS = json.load(json_file)

    # Copy voxel dimensions and padding settings to filter parameter dictionary
    filterTypes = list(paramS['imageType'].keys())
    if scanNum is not None:
        voxelSizemmV = planC.scan[scanNum].getScanSpacing() * 10
        for n in range(len(filterTypes)):
            paramS['imageType'][filterTypes[n]]['VoxelSize_mm'] = voxelSizemmV
            if 'padding' in paramS['settings'].keys():
                paramS['imageType'][filterTypes[n]]['padding'] = paramS['settings']['padding'][0]

    return paramS, filterTypes


def processImage(filterType, scan3M, mask3M, paramS):
    """
    Process scan using selected filter and parameters

    filterType : Name of supported filter
    scan3M     : 3D scan array
    mask3M     : 3D mask
    paramS     : Dictionary of parameters (read from JSON)
    """

    filterType = filterType.strip().lower()
    scan3M = scan3M.astype(float)
    outS = dict()

    if filterType == 'original':
        # Do nothing
        outS['original'] = scan3M

    elif filterType == 'mean':

        absFlag = False
        kernelSize = np.array(paramS['KernelSize'])
        if 'Absolute' in paramS.keys():
            absFlag = paramS['Absolute'].lower() == 'yes'
        mean3M = textureFilters.meanFilter(scan3M, kernelSize, absFlag)
        outS['mean'] = mean3M

    elif filterType == 'sobel':

        mag3M, dir3M = textureFilters.sobelFilter(scan3M)
        outS['SobelMag'] = mag3M
        outS['SobelDir'] = dir3M

    elif filterType == 'log':

        sigmaV = paramS['Sigma_mm']
        cutOffV = np.array(paramS['CutOff_mm'])
        voxelSizeV = np.array(paramS['VoxelSize_mm'])
        LoG3M = textureFilters.LoGFilter(scan3M, sigmaV, cutOffV, voxelSizeV)
        outS['LoG'] = LoG3M

    elif filterType in ['gabor', 'gabor3d']:

        voxelSizV = np.array(paramS['VoxelSize_mm'])
        sigma = paramS['Sigma_mm'] / voxelSizV[0]
        wavelength = paramS['Wavlength_mm'] / voxelSizV[0]
        thetaV = np.array(paramS['Orientation'])
        gamma = paramS['SpatialAspectRatio']
        radius = None
        paddingV = None

        if 'Radius_mm' in paramS.keys():
            radius = np.array([paramS['Radius_mm'],paramS['Radius_mm']])
        if 'Padding' in paramS.keys():
            paddingV = paramS['Padding']['Size']

        if filterType == 'gabor':
            if 'OrientationAggregation' in paramS.keys():
                aggS = {'OrientationAggregation': paramS['OrientationAggregation']}
                outS, __ = textureFilters.gaborFilter(scan3M, sigma, wavelength, gamma, thetaV, aggS, radius, paddingV)
            else:
                outS, __ = textureFilters.gaborFilter(scan3M, sigma, wavelength, gamma, thetaV, radius, paddingV)
        elif filterType == 'gabor3d':
            aggS = {'PlaneAggregation': paramS['PlaneAggregation']}
            if 'OrientationAggregation' in paramS.keys():
                aggS['OrientationAggregation'] = paramS['OrientationAggregation']
            outS, __ = textureFilters.gaborFilter3d(scan3M, sigma, wavelength, gamma, thetaV, aggS, radius, paddingV)

    elif filterType in ['laws', 'rotationinvariantlaws']:

        direction = paramS['Direction']
        type = paramS['Type']
        normFlag = 'false'
        if 'Normalize' in paramS.keys():
            normFlag = paramS['Normalize'].lower()=='yes'
        if filterType == 'laws':
            outS = textureFilters.lawsFilter(scan3M, direction, type, normFlag)
        elif filterType == 'rotationinvariantlaws':
            rotS = paramS['RotationInvariance']
            out3M = textureFilters.rotationInvariantLawsFilter(scan3M, direction, type, normFlag, rotS)
            outS[type] = out3M

    elif filterType in ['lawsenergy', 'rotationinvariantlawsenergy']:

        direction = paramS['Direction']
        type = paramS['Type']
        normFlag = 0
        lawsPadSizeV = np.array([0, 0, 0])
        energyKernelSizeV = paramS['EnergyKernelSize']
        energyPadSizeV = paramS['EnergyPadSize']
        energyPadMethod = paramS['EnergyPadMethod']
        if 'Normalize' in paramS.keys():
            normFlag = paramS['Normalize']
        if 'Padding' in paramS.keys():
            lawsPadFlag = paramS['Padding']['Flag']
            lawsPadSizeV = paramS['Padding']['Size']
            lawsPadMethod = paramS['Padding']['Method']
        if filterType == 'lawsenergy':
            outS = textureFilters.lawsEnergyFilter(scan3M, mask3M, direction, type, normFlag, lawsPadFlag, lawsPadSizeV,\
                                                   lawsPadMethod, energyKernelSizeV, energyPadSizeV, energyPadMethod)
        elif filterType == 'rotationinvariantlawsenergy':
            rotS = paramS['RotationInvariance']
            out3M = textureFilters.rotationInvariantLawsEnergyFilter(scan3M, mask3M, direction, type, normFlag, \
                                                                     lawsPadFlag, lawsPadSizeV, lawsPadMethod, \
                                                                     energyKernelSizeV, energyPadSizeV, \
                                                                     energyPadMethod, rotS)
            outS[type + '_Energy'] = out3M

    # elif filterType in ['wavelets', 'rotationinvariantwavelets']:
    #
    #     waveType = paramS['Wavelets']
    #     direction = paramS['Direction']
    #     level = 1  # Default
    #     if 'level' in paramS.keys():
    #         level = paramS['Level']
    #     if 'Index' in paramS and paramS['Index'] is not None:
    #         waveType += str(paramS['Index'])
    #     if filterType == 'rotationInvariantWaveletFilter':
    #         outS = waveletFilter(scan3M, waveType, direction, level)
    #     # elif filterType == 'rotationInvariantWavelets':

    else:
        raise Exception('Unknown filter name ' + filterType)

    return outS


def generateTextureMapFromPlanC(planC, scanNum, strNum, configFilePath):
    """
    Filter image and add to planC
    planC           : Plan container
    scanNum         : Index of scan to be filtered
    strNum          : Index of ROI
    configFilePath  : Path to JSON config file with filter parameters
    """

    # Extract scan and mask
    if isinstance(strNum, np.ndarray) and scanNum is not None:
        mask3M = strNum
        _, _, slicesV = np.where(mask3M)
        uniqueSlicesV = np.unique(slicesV)
        strName = 'ROI'
    else:
        scanNum = planC.structure[strNum].getStructureAssociatedScan(planC)
        scan3M = planC.scan[scanNum].getScanArray()
        origSizeV = scan3M.shape
        mask3M = np.zeros(origSizeV, dtype=bool)
        rasterSegM = planC.structure[strNum].rasterSegments
        slcMask3M, uniqueSlicesV = rs.raster_to_mask(rasterSegM, scanNum, planC)
        mask3M[:, :, uniqueSlicesV] = slcMask3M
        strName = planC.structure[strNum].structureName

    # Read config file
    paramS, __ = loadSettingsFromFile(configFilePath)

    # Apply preprocessing
    procScan3M, procMask3M, morphmask3M, gridS, __, __ = preProcessForRadiomics(scanNum, strNum, paramS, planC)
    minr, maxr, minc, maxc, mins, maxs, __ = compute_boundingbox(procMask3M)

    # Extract settings to reverse preprocessing transformations
    padFlag = False
    padSizeV = [0,0,0]
    padMethod = "none"
    if 'padding' in paramS["settings"] and paramS["settings"]["padding"]["method"].lower()!='none':
        padSizeV = paramS["settings"]["padding"]["size"]
        padMethod = paramS["settings"]["padding"]["method"]
        padFlag = True

    # Apply filter(s)
    filterTypes = list(paramS['imageType'].keys())
    for filterType in filterTypes:

        # Read filter parameters
        filtParamS = paramS["imageType"][filterType]
        if not isinstance(filtParamS,list):
            filtParamS = [filtParamS]

        for numPar in range(len(filtParamS)):  # Loop over different settings for a filter

            voxSizeV = gridS["PixelSpacingV"]
            currFiltParamS = filtParamS[numPar]
            currFiltParamS["VoxelSize_mm"]  = voxSizeV * 10
            currFiltParamS["Padding"] = {"Size":padSizeV,"Method": padMethod, "Flag": padFlag}

            # Filter scan
            outS = processImage(filterType, procScan3M, procMask3M, currFiltParamS)

            fieldnames = list(outS.keys())

            for nOut in range(len(fieldnames)):

                filtScan3M = outS[fieldnames[nOut]]
                texSizeV = filtScan3M.shape

                # Remove padding
                if currFiltParamS["Padding"]["Method"].lower()=='expand':
                    validPadSizeV = [
                    min(padSizeV[0], minr),
                    min(padSizeV[0], procMask3M.shape[0] - maxr),
                    min(padSizeV[1], minc),
                    min(padSizeV[1], procMask3M.shape[1] - maxc),
                    min(padSizeV[2], mins),
                    min(padSizeV[2], procMask3M.shape[2] - maxs)
                    ]
                else:
                    validPadSizeV = [padSizeV[0],padSizeV[0],padSizeV[1],padSizeV[1],\
                                    padSizeV[2],padSizeV[2]]

                filtScan3M = filtScan3M[validPadSizeV[0]:texSizeV[0] - validPadSizeV[1],
                                        validPadSizeV[2]:texSizeV[1] - validPadSizeV[3],
                                        validPadSizeV[4]:texSizeV[2] - validPadSizeV[5]]

                filtMask3M = procMask3M[validPadSizeV[0]:texSizeV[0] - validPadSizeV[1],
                                        validPadSizeV[2]:texSizeV[1] - validPadSizeV[3],
                                        validPadSizeV[4]:texSizeV[2] - validPadSizeV[5]]

                # Add filter response map to planC
                xV = gridS['xValsV']
                yV = gridS['yValsV']
                zV = gridS['zValsV']
                yV = yV[validPadSizeV[0]:texSizeV[0] - validPadSizeV[1]]
                xV = xV[validPadSizeV[2]:texSizeV[1] - validPadSizeV[3]]
                zV = zV[validPadSizeV[4]:texSizeV[2] - validPadSizeV[5]]

                planC = pc.import_scan_array(filtScan3M, xV, yV, zV, filterType, scanNum, planC)
                #assocScanNum = len(planC.scan)-1
                #assocStrName = 'processed_' + strName
                #strNum = None
                #planC = pc.import_structure_mask(filtMask3M.astype(int), assocScanNum, assocStrName, strNum, planC)

    return planC
