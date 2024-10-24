# pyCERR - A Python-based Computational Environment for Radiological Research

pyCERR provides convenient data structure for imaging metadata and their associations. Utilities are provided to to extract, transform, organize metadata and visualize results of image processing for image and dosimetry features, image processing for AI model training and inference.

## Install Miniconda and Git
It is recommended to install CERR in an isolated environment such as Anaconda or VENV from GitHub repository. Please refer to 
1. https://docs.conda.io/projects/miniconda/en/latest/miniconda-install.html for installing Miniconda and 
2. https://git-scm.com/downloads for installing Git on your system.

## Install pyCERR

Launch Miniconda terminal, create a Conda environment with Python 3.8 and install CERR. Note that CERR requires Python version >= 3.8 to use Napari Viewer.
````
conda create -y --name pycerr python=3.11
conda activate pycerr
pip install "pyCERR[napari] @ git+https://github.com/cerr/pyCERR"
````    
The above steps will install CERR under testcerr/Lib/site-packages. 

Install Jupyter Lab or Notebook to try out example notebooks.
````
pip install jupyterlab
````

## Example Notebooks
Example notebooks are hosted at https://github.com/cerr/pyCERR-Notebooks/ . Clone this repository to use notebooks as a starting point.
````
git clone https://github.com/cerr/pyCERR-Notebooks.git
````

## Example snippets

Run python from the above Anaconda environment and try out the following code samples.

### import modules for planC and viewer
    import numpy as np
    from cerr import plan_container as pc
    from cerr import viewer as vwr

### Read DICOM directory contents to planC
    dcm_dir = r"\\path\to\Data\dicom\directory"
    planC = pc.load_dcm_dir(dcm_dir)
    
### Read NifTi scan to planC
    scanNiiFileName = r"\\path\to\Data\scan.nii.gz"
    planC = pc.load_nii_scan(scanNiiFileName, imageType = "CT SCAN")

### Read NifTi scan to planC by specifying the orientation
    planC = pc.load_nii_scan(scanNiiFileName, imageType = "CT SCAN", direction='HFS')

### Read NifTi scan to planC by appending to an existing planC
    planC = pc.load_nii_scan(scanNiiFileName, imageType = "CT SCAN", direction='HFS', planC)
    
### Read NifTi segmentation to planC
    structNiiFileName = r"\\path\to\Data\structure.nii.gz"
    assocScanNum = 0
    labels_dict = {1: 'GTV_P', 2: 'GTV_N'}
    planC = pc.load_nii_structure(nii_file_name, assocScanNum, planC, labels_dict)

### Export Scan, Structure and Dose to NifTi
    scanNiiFileName = r"\\path\to\Data\scan.nii.gz"
    scanNum = 0
    planC.scan[scanNum].save_nii(scanNiiFileName)
    
    structNiiFileName = r"\\path\to\Data\structure.nii.gz"
    structNum = 0
    planC.structure[structNum].save_nii(structNiiFileName, planC)    
    
    doseNiiFileName = r"\\path\to\Data\dose.nii.gz"
    doseNum = 0
    planC.dose[doseNum].save_nii(doseNiiFileName)
    

### visualize scan, dose and segmentation    
    scanNumList = [0]
    doseNumList = [0]
    numStructs = len(planC.structure)
    strNumList = np.arange(numStructs)
    displayMode = '2d' # '2d' or '3d'
    vectDict = {}
    viewer, scan_layer, dose_layer, struct_layer, dvf_layer = \
            vwr.showNapari(scanNumList, strNumList, doseNumList, vectDict, planC, displayMode)
            

### Compute DVH-based metrics
    from cerr import dvh
    structNum = 0
    doseNum = 0
    dosesV, volsV, isErr = dvh.getDVH(structNum, doseNum, planC)
    binWidth = 0.025
    doseBinsV,volHistV = dvh.doseHist(dosesV, volsV, binWidth)
    percent = 70
    dvh.MOHx(doseBinsV,volHistV,percent)
