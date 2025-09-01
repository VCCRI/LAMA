"""
Script to combine labels from multiple files into one nrdd file based on the number in the filename
format of filename is number--description
Each NRRD file should have only one label in it, otherwise they will all be combined in the new NRRD file
"""
import os
import nrrd
from pathlib import Path
import csv
separator = '--'
label_num = 1

# Directory contining multiple Nrrds each with a label
#folder_with_nrrds = Path('/Volumes/Gavs_T5/APP/Test/temp4')
folder_with_nrrds = '/Volumes/Gavs_T7/APP/E17.5/atlas_split/complete'
outpath = '/Volumes/Gavs_T7/APP/E17.5/E17.5_Atlas20052025.nrrd'
#make a list of all nrrd files
filenames = [fn for fn in os.listdir(folder_with_nrrds) if fn[-5:] == '.nrrd' if not fn.startswith('._')] # os.listdir returns a list
print(filenames)
parentPath = Path(outpath).parent
print(parentPath)
fullcsvPath = parentPath / "labels.csv"
print(fullcsvPath)
#sort filenames so that they are added in order
#really would like to remove file from list that do not start with an integar

filenames.sort(key=lambda x: int(x.split(separator)[0])) # sort list in case file load in wrong order
print(filenames)
print('Loading {} files from {}'.format(len(filenames), folder_with_nrrds))
with open(fullcsvPath, mode='w') as csv_file:
#with open(test.csv, mode='w') as csv_file:
    fieldnames = ['label', 'label_name', 'term']   # header for csv file
    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
    writer.writeheader()
    #loop over nrrd files listed in filenames. Each NRRD files must have unique number followed by -- and have only one label
    for index, fullFileName in enumerate(filenames, start=0):   # default is zero
        print(index, fullFileName)
        try:
            label_num = int(fullFileName.split(separator)[0])
        except:
            print(f'Error, {fullFileName} appears to not start with an integar')
        fileNameNRRD = str(fullFileName.split(separator)[1])   # str is probably not needed here
        cutFileName = fileNameNRRD[:-5]
        writer.writerow({'label': label_num, 'label_name': cutFileName, 'term': 'na'})
        print(f'doing {fullFileName}')  # this print syntax is new in python3.6
        if index == 0:
            # In the first iteration, create an output array starting with the first label array
            input_label_img, head = nrrd.read(folder_with_nrrds + "/" + fullFileName)  # nrrd.read returns data as nd.array and header (as dictionary)
            print(f'label number is {label_num}')
            input_label_img[input_label_img != 0] = label_num # this should combine any other labels into one the NRRD file
            output_array = input_label_img
            # set first label to value of label_num from file name in case already not correct
            output_array[output_array != 0] = label_num

        else:
            input_label_img, head = nrrd.read(folder_with_nrrds + "/" + fullFileName)  # nrrd.read returns data as nd.array and header

            print(f'label number is {label_num}')
            #change input_label_img to the current label_num (derived from file name)
            input_label_img[input_label_img != 0] = label_num # this will remove any other labels in the NRRD file

            # Merge the current label to the outut image
            output_array[input_label_img != 0] = input_label_img[input_label_img != 0] #dont grasp this yet

            #output_array[input_label_img != 0] = label_num

nrrd.write(outpath, output_array, header=head)
# need to sort header as in TIFFsToNRRD.py
