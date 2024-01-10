import json

import numpy as np

import cerr.contour.rasterseg as rs
from cerr import plan_container as pc
from cerr.radiomics import textureFilters
from cerr.radiomics.preprocess import preProcessForRadiomics
from cerr.utils.bbox import compute_boundingbox


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

    if filterType == 'mean':

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

        if 'Radius' in paramS.keys():
            radius = paramS['Radius']
        if 'Padding' in paramS.keys():
            paddingV = paramS['Padding']

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
        normFlag = 0
        if 'Normalize' in paramS.keys():
            normFlag = paramS['Normalize']
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
            lawsPadSizeV = paramS['Padding']
        if filterType == 'lawsenergy':
            outS = textureFilters.lawsEnergyFilter(scan3M, direction, type, normFlag, lawsPadSizeV,
                                                   energyKernelSizeV, energyPadSizeV, energyPadMethod)
        elif filterType == 'rotationinvariantlawsenergy':
            rotS = paramS['RotationInvariance']
            out3M = textureFilters.rotationInvariantLawsEnergyFilter(scan3M, direction, type, normFlag, lawsPadSizeV,
                                                                     energyKernelSizeV, energyPadSizeV, energyPadMethod,
                                                                     rotS)
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
    else:
        scanNum = planC.structure[strNum].getStructureAssociatedScan(planC)[0]
        scan3M = planC.scan[scanNum].getScanArray()
        origSizeV = scan3M.shape
        mask3M = np.zeros(origSizeV, dtype=bool)
        rasterSegM = planC.structure[strNum].rasterSegments
        slcMask3M, uniqueSlicesV = rs.raster_to_mask(rasterSegM, scanNum, planC)
        mask3M[:, :, uniqueSlicesV] = slcMask3M

    # Read config file
    paramS, __ = loadSettingsFromFile(configFilePath)

    # Apply preprocessing
    procScan3M, procMask3M, gridS, __, __ = preProcessForRadiomics(scanNum, strNum, paramS, planC)
    minr, maxr, minc, maxc, mins, maxs, __ = compute_boundingbox(procMask3M)

    # Extract settings to reverse preprocessing transformations
    padSizeV = [0,0,0]
    if 'padding' in paramS["settings"] and len(paramS["settings"]['padding']) > 0:
        padSizeV = paramS["settings"]['padding'][0]['size']

    # Apply filter(s)
    filterTypes = list(paramS['imageType'].keys())
    for filterType in filterTypes:

        # Read filter parameters
        filtParamS = paramS['imageType'][filterType]
        if not isinstance(filtParamS,list):
            filtParamS = [filtParamS]

        for numPar in range(len(filtParamS)):  # Loop over different settings for a filter

            voxSizeV = gridS['PixelSpacingV']
            currFiltParamS = filtParamS[numPar]
            currFiltParamS["VoxelSize_mm"]  = voxSizeV * 10
            currFiltParamS["Padding"] = padSizeV

            # Filter scan
            outS = processImage(filterType, procScan3M, procMask3M, currFiltParamS)

            fieldnames = list(outS.keys())

            for nOut in range(len(fieldnames)):

                filtScan3M = outS[fieldnames[nOut]]
                texSizeV = filtScan3M.shape

                # Remove padding
                validPadSizeV = [
                    min(padSizeV[0], minr),
                    min(padSizeV[0], procMask3M.shape[0] - maxr),
                    min(padSizeV[1], minc),
                    min(padSizeV[1], procMask3M.shape[1] - maxc),
                    min(padSizeV[2], mins),
                    min(padSizeV[2], procMask3M.shape[2] - maxs)
                ]

                filtScan3M = filtScan3M[validPadSizeV[0]:texSizeV[0] - validPadSizeV[1],
                             validPadSizeV[2]:texSizeV[1] - validPadSizeV[3],
                             validPadSizeV[4]:texSizeV[2] - validPadSizeV[5]]

                filtMask3M = procMask3M[validPadSizeV[0] + 1 : texSizeV[0] - validPadSizeV[1],
                                        validPadSizeV[2]:texSizeV[1] - validPadSizeV[3],
                                        validPadSizeV[4]:texSizeV[2] - validPadSizeV[5]]
                [__, __, __, __, mins, maxs, __] = compute_boundingbox(filtMask3M)
                maskSlcV = np.arange(mins,maxs+1,1)

                # Add filter response map to planC
                xV = gridS['xValsV']
                yV = gridS['yValsV']
                zV = gridS['zValsV']
                zV = zV[maskSlcV]

                planC = pc.import_array(filtScan3M, xV, yV, zV, filterType, scanNum, planC)

    return planC
