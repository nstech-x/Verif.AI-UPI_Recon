import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Progress } from "../components/ui/progress";
import { 
  Sparkles, 
  Brain, 
  MessageSquare, 
  TrendingUp, 
  AlertCircle,
  CheckCircle,
  Globe,
  BarChart3,
  Zap
} from "lucide-react";

// Mock AI data
const AI_INSIGHTS = {
  matchSuggestions: [
    {
      rrn: "636397811101710",
      confidence: 94,
      suggestedMatch: "TXN001240",
      reasons: [
        "Amount exact match (₹12,300.00)",
        "Date match (2026-01-13)",
        "Reference number similarity (98%)",
        "Historical pattern match"
      ],
      featureWeights: {
        amount: 35,
        date: 25,
        reference: 30,
        pattern: 10
      }
    },
    {
      rrn: "636397811101711",
      confidence: 78,
      suggestedMatch: "TXN001245",
      reasons: [
        "Amount match within tolerance (±₹50)",
        "Same transaction date",
        "Customer pattern recognized",
        "Merchant category match"
      ],
      featureWeights: {
        amount: 40,
        date: 20,
        customer: 25,
        merchant: 15
      }
    },
    {
      rrn: "636397811101712",
      confidence: 67,
      suggestedMatch: "TXN001250",
      reasons: [
        "Amount within broader tolerance (±₹200)",
        "Date proximity (same week)",
        "Partial reference match"
      ],
      featureWeights: {
        amount: 45,
        date: 30,
        reference: 25
      }
    }
  ],
  clusters: [
    {
      id: "CL001",
      type: "Recurring Pattern",
      count: 23,
      pattern: "Missing CBS entries during 2-3 PM window",
      action: "Check CBS batch processing schedule",
      priority: "high"
    },
    {
      id: "CL002",
      type: "Settlement Delay",
      count: 15,
      pattern: "NPCI settlement delay for specific merchant",
      action: "Flag for manual review",
      priority: "medium"
    }
  ]
};

export default function AIShowcase() {
  const [selectedLanguage, setSelectedLanguage] = useState("en");

  return (
    <div className="p-6 space-y-6">
      {/* Header with Advisory Badge */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-foreground flex items-center gap-2">
              <Sparkles className="w-6 h-6 text-brand-purple" />
              AI Showcase
            </h1>
            <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-200">
              Preview Only
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Preview of Upcoming AI Capabilities (Advisory Only)
          </p>
        </div>
      </div>

      <Tabs defaultValue="match-confidence" className="w-full">
        <TabsList className="bg-muted/30">
          <TabsTrigger value="match-confidence">
            <Brain className="w-4 h-4 mr-2" />
            Match Confidence
          </TabsTrigger>
          <TabsTrigger value="clustering">
            <TrendingUp className="w-4 h-4 mr-2" />
            Exception Clustering
          </TabsTrigger>
          <TabsTrigger value="chatbot">
            <MessageSquare className="w-4 h-4 mr-2" />
            Ask Verif.AI
          </TabsTrigger>
        </TabsList>

        {/* AI Match Confidence Tab */}
        <TabsContent value="match-confidence" className="space-y-4 mt-6">
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <Brain className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-blue-900 mb-1">
                  <strong>AI-Powered Intelligent Matching</strong>
                </p>
                <p className="text-sm text-blue-800">
                  Our advanced AI analyzes multiple transaction features including amounts, dates, references, and historical patterns to suggest potential matches for unmatched transactions. Each suggestion includes an explainable confidence score and detailed reasoning.
                </p>
              </div>
            </div>
          </div>

          {AI_INSIGHTS.matchSuggestions.map((suggestion, idx) => (
            <Card key={idx} className="border-2 hover:shadow-md transition-shadow">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <CardTitle className="text-lg font-semibold">RRN: {suggestion.rrn}</CardTitle>
                    <CardDescription className="text-sm">
                      Suggested Match: <span className="font-medium text-foreground">{suggestion.suggestedMatch}</span>
                    </CardDescription>
                  </div>
                  <div className="text-right">
                    <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold ${
                      suggestion.confidence >= 90 ? 'bg-green-100 text-green-800 border border-green-200' :
                      suggestion.confidence >= 80 ? 'bg-blue-100 text-blue-800 border border-blue-200' :
                      suggestion.confidence >= 70 ? 'bg-yellow-100 text-yellow-800 border border-yellow-200' :
                      'bg-red-100 text-red-800 border border-red-200'
                    }`}>
                      <CheckCircle className="w-4 h-4 mr-1" />
                      {suggestion.confidence}% Confidence
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {suggestion.confidence >= 90 ? 'Very High' :
                       suggestion.confidence >= 80 ? 'High' :
                       suggestion.confidence >= 70 ? 'Medium' :
                       'Low'} Confidence
                    </div>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Enhanced Confidence Visualization */}
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium text-foreground flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-blue-600" />
                      AI Match Confidence
                    </span>
                    <div className="text-right">
                      <span className="text-lg font-bold text-foreground">{suggestion.confidence}%</span>
                      <div className={`text-xs font-medium mt-0.5 ${
                        suggestion.confidence >= 90 ? 'text-green-600' :
                        suggestion.confidence >= 80 ? 'text-blue-600' :
                        suggestion.confidence >= 70 ? 'text-yellow-600' :
                        'text-red-600'
                      }`}>
                        {suggestion.confidence >= 90 ? 'Very High' :
                         suggestion.confidence >= 80 ? 'High' :
                         suggestion.confidence >= 70 ? 'Medium' :
                         'Low'} Confidence
                      </div>
                    </div>
                  </div>
                  <div className="relative">
                    <Progress
                      value={suggestion.confidence}
                      className={`h-3 ${
                        suggestion.confidence >= 90 ? '[&>div]:bg-green-500' :
                        suggestion.confidence >= 80 ? '[&>div]:bg-blue-500' :
                        suggestion.confidence >= 70 ? '[&>div]:bg-yellow-500' :
                        '[&>div]:bg-red-500'
                      }`}
                    />
                    <div className="flex justify-between text-xs text-muted-foreground mt-1">
                      <span>0%</span>
                      <span className="text-center">50%</span>
                      <span>100%</span>
                    </div>
                  </div>
                  <div className="flex justify-center">
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <div className="w-2 h-2 bg-red-400 rounded-full"></div>
                        Low (0-69%)
                      </span>
                      <span className="flex items-center gap-1">
                        <div className="w-2 h-2 bg-yellow-400 rounded-full"></div>
                        Medium (70-79%)
                      </span>
                      <span className="flex items-center gap-1">
                        <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
                        High (80-89%)
                      </span>
                      <span className="flex items-center gap-1">
                        <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                        Very High (90%+)
                      </span>
                    </div>
                  </div>
                </div>

                {/* Enhanced Reasoning Section */}
                <div className="space-y-3">
                  <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
                    <Brain className="w-4 h-4 text-blue-600" />
                    AI Reasoning & Evidence
                  </h4>
                  <div className="grid gap-2">
                    {suggestion.reasons.map((reason, i) => (
                      <div key={i} className="flex items-start gap-3 p-3 bg-green-50 border border-green-100 rounded-lg">
                        <CheckCircle className="w-4 h-4 text-green-600 mt-0.5 flex-shrink-0" />
                        <span className="text-sm text-green-800">{reason}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Enhanced Feature Weights */}
                <div className="space-y-3">
                  <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-purple-600" />
                    Feature Contribution Analysis
                  </h4>
                  <div className="space-y-3">
                    {Object.entries(suggestion.featureWeights).map(([feature, weight]) => (
                      <div key={feature} className="space-y-2">
                        <div className="flex justify-between items-center">
                          <span className="text-sm font-medium text-foreground capitalize">
                            {feature.replace('_', ' ')}
                          </span>
                          <span className="text-sm font-semibold text-purple-600">{weight}%</span>
                        </div>
                        <div className="relative">
                          <Progress
                            value={weight as number}
                            className="h-2 [&>div]:bg-purple-500"
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="text-xs text-muted-foreground text-center pt-2 border-t">
                    Total feature weights should sum to 100%
                  </div>
                </div>

                {/* Action Button */}
                <div className="pt-2">
                  <Button
                    variant="outline"
                    className="w-full h-10 text-sm font-medium border-2 hover:bg-blue-50 hover:border-blue-300 transition-colors"
                    disabled
                  >
                    <Zap className="w-4 h-4 mr-2 text-blue-600" />
                    Apply AI Suggestion (Coming Soon)
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </TabsContent>

        {/* Exception Clustering Tab */}
        <TabsContent value="clustering" className="space-y-4 mt-6">
          <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
            <p className="text-sm text-orange-900">
              <strong>Smart Grouping:</strong> AI identifies patterns in exceptions and clusters similar issues together for efficient resolution.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {AI_INSIGHTS.clusters.map((cluster) => (
              <Card key={cluster.id}>
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-base">{cluster.type}</CardTitle>
                      <CardDescription className="text-xs">{cluster.id}</CardDescription>
                    </div>
                    <Badge 
                      variant={cluster.priority === "high" ? "destructive" : "secondary"}
                      className="text-xs"
                    >
                      {cluster.count} cases
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="space-y-1">
                    <div className="text-sm font-medium">Pattern Detected:</div>
                    <div className="text-sm text-muted-foreground">{cluster.pattern}</div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-sm font-medium">Suggested Action:</div>
                    <div className="text-sm text-muted-foreground">{cluster.action}</div>
                  </div>
                  <div className="flex items-center gap-2 pt-2">
                    <AlertCircle className={`w-4 h-4 ${cluster.priority === "high" ? "text-red-600" : "text-orange-600"}`} />
                    <span className="text-xs font-medium capitalize">{cluster.priority} Priority</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Chatbot Tab */}
        <TabsContent value="chatbot" className="space-y-4 mt-6">
          <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
            <p className="text-sm text-purple-900">
              <strong>Ask Verif.AI:</strong> Intelligent chatbot for transaction queries, dispute guidance, and system FAQs with multilingual support.
            </p>
          </div>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Chatbot Features</CardTitle>
                <div className="flex items-center gap-2">
                  <Globe className="w-4 h-4 text-muted-foreground" />
                  <select 
                    value={selectedLanguage}
                    onChange={(e) => setSelectedLanguage(e.target.value)}
                    className="text-sm border rounded px-2 py-1"
                  >
                    <option value="en">English</option>
                    <option value="hi">हिंदी</option>
                    <option value="ta">தமிழ்</option>
                    <option value="te">తెలుగు</option>
                  </select>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="border rounded-lg p-4 space-y-2">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="w-5 h-5 text-brand-blue" />
                    <h4 className="font-medium">FAQ Support</h4>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Instant answers to frequently asked questions about reconciliation processes
                  </p>
                </div>

                <div className="border rounded-lg p-4 space-y-2">
                  <div className="flex items-center gap-2">
                    <AlertCircle className="w-5 h-5 text-brand-blue" />
                    <h4 className="font-medium">Enquiry</h4>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Step-by-step guidance for resolving disputes and exceptions
                  </p>
                </div>

                <div className="border rounded-lg p-4 space-y-2">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-brand-blue" />
                    <h4 className="font-medium">Status Queries</h4>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Real-time transaction status and reconciliation progress
                  </p>
                </div>

                <div className="border rounded-lg p-4 space-y-2">
                  <div className="flex items-center gap-2">
                    <Globe className="w-5 h-5 text-brand-blue" />
                    <h4 className="font-medium">Multilingual</h4>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Support for multiple Indian languages for better accessibility
                  </p>
                </div>
              </div>

              <div className="bg-muted/30 rounded-lg p-4 space-y-2">
                <h4 className="text-sm font-medium">Example Queries:</h4>
                <div className="space-y-1 text-sm text-muted-foreground">
                  <div>• "How do I reconcile a transaction?"</div>
                  <div>• "What is a hanging transaction?"</div>
                  <div>• "How to resolve amount mismatch?"</div>
                  <div>• "Show status of RRN 636397811101708"</div>
                </div>
              </div>

              <Button variant="outline" className="w-full" disabled>
                Launch Chatbot (Coming Soon)
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}