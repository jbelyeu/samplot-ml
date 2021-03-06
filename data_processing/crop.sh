#!/bin/bash
#SBATCH -p short
#SBATCH --job-name=cropping
#SBATCH --mail-type=ALL
#SBATCH --mail-user=much8161@colorado.edu
#SBATCH --nodes=1
#SBATCH --ntasks=64
#SBATCH --mem=64gb
#SBATCH --time=24:00:00               # Time limit hrs:min:sec
#SBATCH --output=/Users/much8161/Repositories/samplot-ml/data_processing/crop.out
#SBATCH --error=/Users/much8161/Repositories/samplot-ml/data_processing/crop.err


# script to take samplot image and crop out the
# axes, title, etc.
function crop
{
    file_name=$1
    img_dir=$2
    crop_dir=$3

    p=$img_dir/$file_name

    b=`basename $p .png`
    o=$crop_dir/${b}.png

    if [ ! -f $o ]; then
        # crop image if we haven't yet
        convert \
            -crop 2090x575+175+200 \
            -fill white \
            -draw "rectangle 0,30 500,50" \
            -draw "rectangle 600,0 700,50" \
            $p $o
    fi

    echo $o

}

export -f crop

while (( "$#" )); do
    case "$1" in
        -p|--processes)
            PROC=$2
            shift 2;;
        -d|--data-dir)
            DATA_DIR=$2
            shift 2;;
        -o|--out-dir)
            OUT_DIR=$2
            shift 2;;
        --) # end argument parsing
            shift
            break;;
        -*|--*=) # unsupported flags
            echo "Error: Unsupported flag $1" >&2
            exit 1;;
    esac
done
[[ -z $PROC ]] && echo Missing argument --processes && exit 1
[[ -z $DATA_DIR ]] && echo Missing argument --data-dir && exit 1

SCRIPT_DIR=$PWD
# DATA_DIR=/scratch/Shares/layer/projects/samplot/ml/data/1kg/high_cov

cd $DATA_DIR
ls -U $DATA_DIR | gargs -p $PROC "crop {0} $DATA_DIR $OUT_DIR"
cd $SCRIPT_DIR
