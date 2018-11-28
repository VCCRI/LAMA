args <- commandArgs(trailingOnly = TRUE);

pval_file <- args[1]
dim <- as.integer(args[2])
qvals_out <- args[3]

con <- file(pval_file, "rb")
mat <- readBin(con, "double", n=dim, size=4)
close(con)
out <- p.adjust(mat, method='BH')
writeBin(out, qvals_out)