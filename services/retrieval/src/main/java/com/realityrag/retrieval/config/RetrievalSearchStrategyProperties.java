package com.realityrag.retrieval.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "retrieval.search")
public class RetrievalSearchStrategyProperties {
    private int fusedTopM = 60;
    private boolean enableRerank = true;
    private int rerankTopN = 10;
    private int maxRerankChars = 1000;
    private int maxBreadcrumbChars = 250;
    private double headRatio = 0.67d;
    private boolean enableRagflowRerankWindow = true;
    private int ragflowRerankWindowMin = 30;
    private int ragflowRerankWindowMax = 64;
    private boolean enableRagflowTokenWeighting = true;
    private int ragflowTitleTokenWeight = 2;
    private int ragflowImportantKeywordWeight = 5;
    private int ragflowQuestionTokenWeight = 6;
    private boolean enableRagflowRankFeatures = true;
    private boolean enableRagflowKeywordExtraction = true;
    private int ragflowKeywordTopN = 3;
    private boolean enableRagflowCrossLanguages = true;
    private boolean enableRagflowMetadataAutoFilter = true;
    private boolean enableRagflowChildrenAggregation = true;
    private boolean enableRagflowTocAggregation = true;
    private boolean enableRagflowTocLlmSelector = true;
    private int ragflowTocTopN = 6;
    private double ragflowTocMinScore = 0.3d;
    private boolean enableSmartTopK = true;
    private double smartTopScoreRatio = 0.5d;
    private double smartTopScoreDeltaAbs = 0.25d;
    private double smartMinScore = 0.25d;
    private int smartMinK = 2;
    private int smartMaxK = 8;
    private boolean enableNeighborExpansion = true;
    private int neighborHops = 2;
    private double decayNeighbor = 0.8d;
    private boolean enableBreadcrumbExpansion = true;
    private int breadcrumbExpandLimit = 3;
    private double decayBreadcrumb = 0.7d;
    private int maxSegmentsPerFile = 3;
    private int maxTotalChars = 48000;

    public int getFusedTopM() {
        return fusedTopM;
    }

    public void setFusedTopM(int fusedTopM) {
        this.fusedTopM = fusedTopM;
    }

    public boolean isEnableRerank() {
        return enableRerank;
    }

    public void setEnableRerank(boolean enableRerank) {
        this.enableRerank = enableRerank;
    }

    public int getRerankTopN() {
        return rerankTopN;
    }

    public void setRerankTopN(int rerankTopN) {
        this.rerankTopN = rerankTopN;
    }

    public int getMaxRerankChars() {
        return maxRerankChars;
    }

    public void setMaxRerankChars(int maxRerankChars) {
        this.maxRerankChars = maxRerankChars;
    }

    public int getMaxBreadcrumbChars() {
        return maxBreadcrumbChars;
    }

    public void setMaxBreadcrumbChars(int maxBreadcrumbChars) {
        this.maxBreadcrumbChars = maxBreadcrumbChars;
    }

    public double getHeadRatio() {
        return headRatio;
    }

    public void setHeadRatio(double headRatio) {
        this.headRatio = headRatio;
    }

    public boolean isEnableRagflowRerankWindow() {
        return enableRagflowRerankWindow;
    }

    public void setEnableRagflowRerankWindow(boolean enableRagflowRerankWindow) {
        this.enableRagflowRerankWindow = enableRagflowRerankWindow;
    }

    public int getRagflowRerankWindowMin() {
        return ragflowRerankWindowMin;
    }

    public void setRagflowRerankWindowMin(int ragflowRerankWindowMin) {
        this.ragflowRerankWindowMin = ragflowRerankWindowMin;
    }

    public int getRagflowRerankWindowMax() {
        return ragflowRerankWindowMax;
    }

    public void setRagflowRerankWindowMax(int ragflowRerankWindowMax) {
        this.ragflowRerankWindowMax = ragflowRerankWindowMax;
    }

    public boolean isEnableRagflowTokenWeighting() {
        return enableRagflowTokenWeighting;
    }

    public void setEnableRagflowTokenWeighting(boolean enableRagflowTokenWeighting) {
        this.enableRagflowTokenWeighting = enableRagflowTokenWeighting;
    }

    public int getRagflowTitleTokenWeight() {
        return ragflowTitleTokenWeight;
    }

    public void setRagflowTitleTokenWeight(int ragflowTitleTokenWeight) {
        this.ragflowTitleTokenWeight = ragflowTitleTokenWeight;
    }

    public int getRagflowImportantKeywordWeight() {
        return ragflowImportantKeywordWeight;
    }

    public void setRagflowImportantKeywordWeight(int ragflowImportantKeywordWeight) {
        this.ragflowImportantKeywordWeight = ragflowImportantKeywordWeight;
    }

    public int getRagflowQuestionTokenWeight() {
        return ragflowQuestionTokenWeight;
    }

    public void setRagflowQuestionTokenWeight(int ragflowQuestionTokenWeight) {
        this.ragflowQuestionTokenWeight = ragflowQuestionTokenWeight;
    }

    public boolean isEnableRagflowRankFeatures() {
        return enableRagflowRankFeatures;
    }

    public void setEnableRagflowRankFeatures(boolean enableRagflowRankFeatures) {
        this.enableRagflowRankFeatures = enableRagflowRankFeatures;
    }

    public boolean isEnableRagflowKeywordExtraction() {
        return enableRagflowKeywordExtraction;
    }

    public void setEnableRagflowKeywordExtraction(boolean enableRagflowKeywordExtraction) {
        this.enableRagflowKeywordExtraction = enableRagflowKeywordExtraction;
    }

    public int getRagflowKeywordTopN() {
        return ragflowKeywordTopN;
    }

    public void setRagflowKeywordTopN(int ragflowKeywordTopN) {
        this.ragflowKeywordTopN = ragflowKeywordTopN;
    }

    public boolean isEnableRagflowCrossLanguages() {
        return enableRagflowCrossLanguages;
    }

    public void setEnableRagflowCrossLanguages(boolean enableRagflowCrossLanguages) {
        this.enableRagflowCrossLanguages = enableRagflowCrossLanguages;
    }

    public boolean isEnableRagflowMetadataAutoFilter() {
        return enableRagflowMetadataAutoFilter;
    }

    public void setEnableRagflowMetadataAutoFilter(boolean enableRagflowMetadataAutoFilter) {
        this.enableRagflowMetadataAutoFilter = enableRagflowMetadataAutoFilter;
    }

    public boolean isEnableRagflowChildrenAggregation() {
        return enableRagflowChildrenAggregation;
    }

    public void setEnableRagflowChildrenAggregation(boolean enableRagflowChildrenAggregation) {
        this.enableRagflowChildrenAggregation = enableRagflowChildrenAggregation;
    }

    public boolean isEnableRagflowTocAggregation() {
        return enableRagflowTocAggregation;
    }

    public void setEnableRagflowTocAggregation(boolean enableRagflowTocAggregation) {
        this.enableRagflowTocAggregation = enableRagflowTocAggregation;
    }

    public boolean isEnableRagflowTocLlmSelector() {
        return enableRagflowTocLlmSelector;
    }

    public void setEnableRagflowTocLlmSelector(boolean enableRagflowTocLlmSelector) {
        this.enableRagflowTocLlmSelector = enableRagflowTocLlmSelector;
    }

    public int getRagflowTocTopN() {
        return ragflowTocTopN;
    }

    public void setRagflowTocTopN(int ragflowTocTopN) {
        this.ragflowTocTopN = ragflowTocTopN;
    }

    public double getRagflowTocMinScore() {
        return ragflowTocMinScore;
    }

    public void setRagflowTocMinScore(double ragflowTocMinScore) {
        this.ragflowTocMinScore = ragflowTocMinScore;
    }

    public boolean isEnableSmartTopK() {
        return enableSmartTopK;
    }

    public void setEnableSmartTopK(boolean enableSmartTopK) {
        this.enableSmartTopK = enableSmartTopK;
    }

    public double getSmartTopScoreRatio() {
        return smartTopScoreRatio;
    }

    public void setSmartTopScoreRatio(double smartTopScoreRatio) {
        this.smartTopScoreRatio = smartTopScoreRatio;
    }

    public double getSmartTopScoreDeltaAbs() {
        return smartTopScoreDeltaAbs;
    }

    public void setSmartTopScoreDeltaAbs(double smartTopScoreDeltaAbs) {
        this.smartTopScoreDeltaAbs = smartTopScoreDeltaAbs;
    }

    public double getSmartMinScore() {
        return smartMinScore;
    }

    public void setSmartMinScore(double smartMinScore) {
        this.smartMinScore = smartMinScore;
    }

    public int getSmartMinK() {
        return smartMinK;
    }

    public void setSmartMinK(int smartMinK) {
        this.smartMinK = smartMinK;
    }

    public int getSmartMaxK() {
        return smartMaxK;
    }

    public void setSmartMaxK(int smartMaxK) {
        this.smartMaxK = smartMaxK;
    }

    public boolean isEnableNeighborExpansion() {
        return enableNeighborExpansion;
    }

    public void setEnableNeighborExpansion(boolean enableNeighborExpansion) {
        this.enableNeighborExpansion = enableNeighborExpansion;
    }

    public int getNeighborHops() {
        return neighborHops;
    }

    public void setNeighborHops(int neighborHops) {
        this.neighborHops = neighborHops;
    }

    public double getDecayNeighbor() {
        return decayNeighbor;
    }

    public void setDecayNeighbor(double decayNeighbor) {
        this.decayNeighbor = decayNeighbor;
    }

    public boolean isEnableBreadcrumbExpansion() {
        return enableBreadcrumbExpansion;
    }

    public void setEnableBreadcrumbExpansion(boolean enableBreadcrumbExpansion) {
        this.enableBreadcrumbExpansion = enableBreadcrumbExpansion;
    }

    public int getBreadcrumbExpandLimit() {
        return breadcrumbExpandLimit;
    }

    public void setBreadcrumbExpandLimit(int breadcrumbExpandLimit) {
        this.breadcrumbExpandLimit = breadcrumbExpandLimit;
    }

    public double getDecayBreadcrumb() {
        return decayBreadcrumb;
    }

    public void setDecayBreadcrumb(double decayBreadcrumb) {
        this.decayBreadcrumb = decayBreadcrumb;
    }

    public int getMaxSegmentsPerFile() {
        return maxSegmentsPerFile;
    }

    public void setMaxSegmentsPerFile(int maxSegmentsPerFile) {
        this.maxSegmentsPerFile = maxSegmentsPerFile;
    }

    public int getMaxTotalChars() {
        return maxTotalChars;
    }

    public void setMaxTotalChars(int maxTotalChars) {
        this.maxTotalChars = maxTotalChars;
    }
}
