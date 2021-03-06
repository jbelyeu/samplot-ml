#!/bin/bash
# Used on c5d ec2 instance to annotate the 1000 genomes SV callset with
# duphold metrics so that we can filter out possible false positives

set -u

function duphold_sample
{
    set -eu

    # TODO add kwargs
    cram_url=$1
    cram_dir=$2
    callset_vcf=$3
    fasta=$4
    out_dir=$5

    cram_file=$cram_dir/$(basename $cram_url)
    sample=$(basename $cram_file | cut -d'.' -f1)

    out_vcf=$out_dir/$sample.duphold.vcf.gz

    # download cram/crai
    if [[ ! -f $cram_file ]]; then
        aws s3 cp $cram_url $cram_dir
        aws s3 cp $cram_url.crai $cram_dir
    fi

    # annotate with duphold
    duphold -d \
        -v $callset_vcf \
        -b $cram_file \
        -f $fasta \
        -o $out_vcf
    tabix $out_vcf

    # upload to s3
    aws s3 cp $out_vcf s3://layerlab/samplot-ml/1kg/duphold_callset/
    aws s3 cp $out_vcf.tbi s3://layerlab/samplot-ml/1kg/duphold_callset/

    # cleanup files
    rm $cram_file $cram_file.crai $out_vcf $out_vcf.tbi
}
export -f duphold_sample
# -----------------------------------------------------------------------------

mkdir /mnt/local/data
mkdir /mnt/local/data/CRAM
mkdir /mnt/local/data/ref
mkdir /mnt/local/data/VCF
mkdir /mnt/local/data/VCF/output

cram_dir=/mnt/local/data/CRAM
ref_dir=/mnt/local/data/ref
vcf_dir=/mnt/local/data/VCF
out_dir=/mnt/local/data/VCF/output

n_tasks=$1

echo "Downloading reference genome..."
if [[ ! -f $ref_dir/GRCh38_full_analysis_set_plus_decoy_hla.fa ]]; then
    aws s3 cp s3://1000genomes/technical/reference/GRCh38_reference_genome/GRCh38_full_analysis_set_plus_decoy_hla.fa $ref_dir
    aws s3 cp s3://1000genomes/technical/reference/GRCh38_reference_genome/GRCh38_full_analysis_set_plus_decoy_hla.fa.fai $ref_dir
fi
fasta=$ref_dir/GRCh38_full_analysis_set_plus_decoy_hla.fa

echo "Downloading 1kg SV callset VCF..."
aws s3 cp s3://1000genomes/phase3/integrated_sv_map/supporting/GRCh38_positions/ALL.wgs.integrated_sv_map_v1_GRCh38.20130502.svs.genotypes.vcf.gz $vcf_dir
callset_vcf=$vcf_dir/ALL.wgs.integrated_sv_map_v1_GRCh38.20130502.svs.genotypes.vcf.gz
tabix $callset_vcf

# rename chromosomes so that they have 'chr' prefix
bcftools view -h $callset_vcf | perl -lne 'if ( /^##contig=<ID=(.+),/ ) { print "$1\tchr$1"; }' > $vcf_dir/chr-map
bcftools annotate --rename-chrs $vcf_dir/chr-map $callset_vcf | bgzip -c > $vcf_dir/fixed.vcf.gz
tabix $vcf_dir/fixed.vcf.gz
callset_vcf=$vcf_dir/fixed.vcf.gz

cat ../data_listings/1kg_high_cov_crams_s3.txt \
    | gargs -p $n_tasks "duphold_sample {} $cram_dir $callset_vcf $fasta $out_dir"





