#!/usr/bin/env python3
"""
script to

"""

#written by anton
import nrrd
from pathlib import Path
import numpy as np

def average(indir, outdir):

    # Directory conatining multiple NRRDs each with a label
    folder_with_nrrds = Path(indir)
    outPath = Path(outdir)
    outpath32bit = outPath / 'Weighted_Average-32bit.nrrd'
    outpath8bit = outPath / 'Weighted_Average-8bit.nrrd'
     
    # loop over all NRRDs in the folder. Make sure nothing else is in there
    for imageNumber, imagePath in enumerate(folder_with_nrrds.iterdir()):
        print(f'doing {imagePath}')  # this print syntax is new in python3.6
        imageArray, head = nrrd.read(imagePath)  # nrrd.read returns data as nd.array and header (not sure as what)
     
        mean_n = np.mean(imageArray)
       
        print(f"mean_{imageNumber} = {mean_n}")
     
        if imageNumber == 0:
            # In the first iteration, create an output array based on the first image array
            output_array = np.array([imageArray])
            mean_0 = mean_n
     
        else:
            print(f"ratio_{imageNumber} = {mean_0/mean_n}")
           
            imageArray = imageArray*(mean_0/mean_n)
           
            print((output_array).shape)
            print((imageArray).shape)
            output_array = np.concatenate([output_array,  np.array([imageArray])], axis=0)
            print((output_array).shape)
           
    output_array = np.average(output_array, axis=0) #average 4D array along axis 0 to create averaged 3d array, output_array will be float
    nrrd.write(str(outpath32bit), output_array, header=head)
    rounded = np.around(output_array) #rounding float values is needed, otherwise 55.99 would end up as 55 in 8bit file with straight casting
    arr_cast = rounded.astype(np.uint8) #cast as 8bit (without scaling values to fit 8-bit)
    head['type'] = 'uint8' # not sure this is needed
    nrrd.write(str(outpath8bit), arr_cast, header=head)



def main():
    import argparse
    parser = argparse.ArgumentParser("average NRRD files with 8bit output")
    parser.add_argument('-i', dest='indir', help='dir with NRRD files to average.', required=True)
    parser.add_argument('-o', dest='outdir', help='dir to put average NRRD file.', required=True)
    args = parser.parse_args()
    average(args.indir, args.outdir)

if __name__ == '__main__':
    main()