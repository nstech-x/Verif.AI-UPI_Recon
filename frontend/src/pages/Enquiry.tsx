import React, { useState, useEffect, useRef, ReactNode } from "react";
import { Card, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Send, Search } from "lucide-react";
import { ScrollArea } from "../components/ui/scroll-area";
import { Badge } from "../components/ui/badge";
import { apiClient } from "../lib/api";

interface Message {
  id: number;
  role: "user" | "bot";
  content: string | ReactNode;
  timestamp: Date;
}

const FAQS = [
  { question: "How do I reconcile a transaction?", answer: "Upload your CBS, Switch, and NPCI files through the File Upload page. The system will automatically match transactions across all three systems and generate reconciliation reports." },
  { question: "What is a hanging transaction?", answer: "A hanging transaction is one that appears in one system but not in others. For example, if a transaction is in CBS but missing in Switch or NPCI, it's considered hanging." },
  { question: "How to resolve amount mismatch?", answer: "For amount mismatches, use the Force-Match tool to review the discrepancy. You can manually verify and match transactions if the difference is within acceptable tolerance." },
  { question: "What are partial matches?", answer: "Partial matches occur when transactions exist in multiple systems but have minor discrepancies like amount or date differences. These can often be resolved through Force-Match." },
  { question: "How to download TTUM reports?", answer: "Go to the Reports page, select 'TTUM & Annexure' category, choose your desired report format (CSV/XLSX), and click Download." },
  { question: "What is the difference between matched and unmatched?", answer: "Matched transactions have identical records across CBS, Switch, and NPCI. Unmatched transactions have discrepancies or are missing from one or more systems." }
];

const EXAMPLE_QUERIES = [
  "Show status of RRN 636397811101708",
  "How do I reconcile a transaction?",
  "What is a hanging transaction?",
  "How to resolve amount mismatch?"
];

export default function Enquiry() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 1,
      role: "bot",
      content: "Hello! I'm Verif.AI, your intelligent UPI Reconciliation Assistant. I can help you with transaction queries, dispute guidance, and system FAQs. Ask me anything!",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [showSuggestion, setShowSuggestion] = useState(true);
  const [selectedLanguage, setSelectedLanguage] = useState("English");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleFAQClick = (faq: typeof FAQS[0]) => {
    const userMsg: Message = { id: messages.length + 1, role: "user", content: faq.question, timestamp: new Date() };
    setMessages((prev) => [...prev, userMsg]);
    setIsTyping(true);
    setTimeout(() => {
      const botMsg: Message = { id: messages.length + 2, role: "bot", content: faq.answer, timestamp: new Date() };
      setMessages((prev) => [...prev, botMsg]);
      setIsTyping(false);
    }, 500);
  };

  const handleExampleClick = (example: string) => {
    setInput(example);
  };

  const formatTransactionDetails = (details: any, rrn: string, status: string) => {
    // Build a JSX element with structured sections so the UI renders nicely
    return (
      <div className="space-y-3 w-full">
        <div className="p-3 rounded-md bg-muted">
          <div className="flex items-center justify-between gap-4">
            <div className="flex-1">
              <div className="text-sm font-semibold">RRN (12-digit Reference)</div>
              <div className="font-mono text-lg font-bold">{rrn || details.rrn || 'N/A'}</div>
            </div>
            <div className="flex-1">
              <div className="text-sm font-semibold">UPI Transaction ID</div>
              <div className="font-mono text-sm">{details.reference || details.upi_tran_id || details.UPI_Tran_ID || 'N/A'}</div>
            </div>
            <div className="text-right">
              <div className="text-sm font-semibold">Status</div>
                <div className="font-semibold">
                  {
                    (() => {
                      const s = (status || details.status || 'UNKNOWN').toString().toUpperCase();
                      const classMap: Record<string,string> = {
                        'MATCHED': 'bg-green-500 text-white px-2 py-0.5 rounded-full text-xs',
                        'FULL_MATCH': 'bg-green-500 text-white px-2 py-0.5 rounded-full text-xs',
                        'PARTIAL': 'bg-yellow-400 text-black px-2 py-0.5 rounded-full text-xs',
                        'PARTIAL_MATCH': 'bg-yellow-400 text-black px-2 py-0.5 rounded-full text-xs',
                        'HANGING': 'bg-orange-400 text-black px-2 py-0.5 rounded-full text-xs',
                        'MISMATCH': 'bg-red-500 text-white px-2 py-0.5 rounded-full text-xs'
                      };
                      const cls = classMap[s] || 'bg-gray-300 text-black px-2 py-0.5 rounded-full text-xs';
                      return <span className={cls}>{s}</span>;
                    })()
                  }
                </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="p-3 rounded-md bg-white border">
            <div className="text-sm font-semibold mb-2">CBS</div>
            {details.cbs ? (
              <div className="text-xs">
                <div>Amount: ₹{Number(details.cbs.amount || 0).toLocaleString()}</div>
                <div>Date: {details.cbs.date || 'N/A'}</div>
                <div>Dr/Cr: {details.cbs.dr_cr || 'N/A'}</div>
                <div>RC: {details.cbs.rc || 'N/A'}</div>
                <div>Type: {details.cbs.tran_type || 'N/A'}</div>
              </div>
            ) : (
              <div className="text-xs text-muted-foreground">Not found</div>
            )}
          </div>

          <div className="p-3 rounded-md bg-white border">
            <div className="text-sm font-semibold mb-2">Switch</div>
            {details.switch ? (
              <div className="text-xs">
                <div>Amount: ₹{Number(details.switch.amount || 0).toLocaleString()}</div>
                <div>Date: {details.switch.date || 'N/A'}</div>
                <div>Type: {details.switch.tran_type || 'N/A'}</div>
              </div>
            ) : (
              <div className="text-xs text-muted-foreground">Not found</div>
            )}
          </div>

          <div className="p-3 rounded-md bg-white border">
            <div className="text-sm font-semibold mb-2">NPCI</div>
            {details.npci ? (
              <div className="text-xs">
                <div>Amount: ₹{Number(details.npci.amount || 0).toLocaleString()}</div>
                <div>Date: {details.npci.date || 'N/A'}</div>
              </div>
            ) : (
              <div className="text-xs text-muted-foreground">Not found</div>
            )}
          </div>
        </div>

        <div className="p-3 rounded-md bg-white border">
          <div className="text-sm font-semibold mb-2">Recon metadata</div>
          <div className="text-xs">Run: {details.recon_run_id || 'N/A'}</div>
          <div className="text-xs">Direction: {details.direction || 'N/A'}</div>
        </div>

        {/* Related / previous transactions (if present in record) */}
        {(details.previous || details.related || details.related_transactions || details.history) && (
          <div className="p-3 rounded-md bg-white border">
            <div className="text-sm font-semibold mb-2">Related / Previous Transactions</div>
            <div className="text-xs space-y-2">
              {(details.previous || details.related || details.related_transactions || details.history).map((r: any, i: number) => (
                <div key={i} className="p-2 border rounded-sm bg-muted/50">
                  <div className="font-mono text-xs">RRN: {r.rrn || r.RRN || 'N/A'}</div>
                  <div className="text-xs">Status: {r.status || 'N/A'}</div>
                  <div className="text-xs">Amount: ₹{Number(r.amount || r.cbs?.amount || 0).toLocaleString()}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        <details className="p-3 rounded-md bg-white border">
          <summary className="cursor-pointer text-sm font-semibold">Raw record (expand)</summary>
          <pre className="text-xs whitespace-pre-wrap mt-2">{JSON.stringify(details, null, 2)}</pre>
        </details>
      </div>
    );
  };

  const handleSend = async () => {
    if (!input.trim()) return;

    setShowSuggestion(false);
    const userMessage: Message = {
      id: messages.length + 1,
      role: "user",
      content: input,
      timestamp: new Date(),
    };

    setMessages([...messages, userMessage]);
    const currentInput = input;
    setInput("");
    setIsTyping(true);

    try {
      let response;

      // Detect a 12-digit RRN anywhere in the text (e.g. "hi check rrn 355481530062")
      const rrnMatch = currentInput.match(/\b(\d{12})\b/);
      if (rrnMatch) {
        response = await apiClient.getChatbotByRRN(rrnMatch[1]);
      } else {
        // Detect common TXN id patterns like 'TXN001', 'txn 001', 'transaction 123'
        const txnMatch = currentInput.match(/\b(?:txn[_\- ]?|transaction[_ ]?|trx[_ ]?)(\d+)\b/i);
        if (txnMatch) {
          response = await apiClient.getChatbotByTxnId(txnMatch[1]);
        } else if (/^\d+$/.test(currentInput.trim())) {
          // Pure numeric input -> treat as txn id
          response = await apiClient.getChatbotByTxnId(currentInput.trim());
        } else {
          // No identifier found in text — try sending as-is to txn endpoint (fallback)
          response = await apiClient.getChatbotByTxnId(currentInput.trim());
        }
      }

      const botMessage: Message = {
        id: messages.length + 2,
        role: "bot",
        content: response?.details
          ? (response.details.error
              ? `❌ ${response.details.message || response.details.error}`
              : formatTransactionDetails(response.details, response.rrn || (rrnMatch ? rrnMatch[1] : currentInput), response.details.status || 'UNKNOWN')
            )
          : `Transaction ${rrnMatch ? rrnMatch[1] : currentInput} not found in the reconciliation data.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, botMessage]);
    } catch (error: any) {
      const errorMessage: Message = {
        id: messages.length + 2,
        role: "bot",
        content: `Sorry, I couldn't find information for "${currentInput}". Please try a valid 12-digit RRN or Transaction ID.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    setInput(suggestion);
    setShowSuggestion(false);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Ask Verif.AI</h1>
          <p className="text-muted-foreground">
            Intelligent chatbot for transaction queries, dispute guidance, and system FAQs
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Language:</span>
          <div className="flex gap-1">
            {["English", "हिंदी", "தமிழ்", "తెలుగు"].map((lang) => (
              <Button
                key={lang}
                variant={selectedLanguage === lang ? "default" : "outline"}
                size="sm"
                onClick={() => setSelectedLanguage(lang)}
                className={selectedLanguage === lang ? "bg-brand-blue text-white" : ""}
              >
                {lang}
              </Button>
            ))}
          </div>
        </div>
      </div>

      {/* Features Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="border-blue-200 bg-blue-50">
          <CardContent className="pt-6">
            <div className="flex flex-col items-center text-center space-y-2">
              <div className="w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center">
                <Search className="w-6 h-6 text-brand-blue" />
              </div>
              <h3 className="font-semibold text-sm">FAQ Support</h3>
              <p className="text-xs text-muted-foreground">
                Instant answers to frequently asked questions
              </p>
            </div>
          </CardContent>
        </Card>
        
        <Card className="border-green-200 bg-green-50">
          <CardContent className="pt-6">
            <div className="flex flex-col items-center text-center space-y-2">
              <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center">
                <span className="text-2xl">✓</span>
              </div>
              <h3 className="font-semibold text-sm">Enquiry</h3>
              <p className="text-xs text-muted-foreground">
                Step-by-step guidnce for resolving enquiries
              </p>
            </div>
          </CardContent>
        </Card>
        
        <Card className="border-purple-200 bg-purple-50">
          <CardContent className="pt-6">
            <div className="flex flex-col items-center text-center space-y-2">
              <div className="w-12 h-12 rounded-full bg-purple-100 flex items-center justify-center">
                <span className="text-2xl">⚡</span>
              </div>
              <h3 className="font-semibold text-sm">Status Queries</h3>
              <p className="text-xs text-muted-foreground">
                Real-time transaction status
              </p>
            </div>
          </CardContent>
        </Card>
        
        <Card className="border-orange-200 bg-orange-50">
          <CardContent className="pt-6">
            <div className="flex flex-col items-center text-center space-y-2">
              <div className="w-12 h-12 rounded-full bg-orange-100 flex items-center justify-center">
                <span className="text-2xl">🌐</span>
              </div>
              <h3 className="font-semibold text-sm">Multilingual</h3>
              <p className="text-xs text-muted-foreground">
                Support for multiple Indian languages
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* FAQs and Example Queries */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* FAQs Section */}
        <Card>
          <CardContent className="pt-6">
            <h3 className="font-semibold text-lg mb-4">Frequently Asked Questions</h3>
            <div className="space-y-2">
              {FAQS.map((faq, idx) => (
                <Button
                  key={idx}
                  variant="outline"
                  className="w-full justify-start text-left h-auto py-3 px-4 hover:bg-brand-light"
                  onClick={() => handleFAQClick(faq)}
                >
                  <span className="text-sm">{faq.question}</span>
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Example Queries */}
        <Card>
          <CardContent className="pt-6">
            <h3 className="font-semibold text-lg mb-4">Example Queries</h3>
            <div className="space-y-2">
              {EXAMPLE_QUERIES.map((example, idx) => (
                <Button
                  key={idx}
                  variant="outline"
                  className="w-full justify-start text-left h-auto py-3 px-4 hover:bg-brand-light"
                  onClick={() => handleExampleClick(example)}
                >
                  <span className="text-sm">"{example}"</span>
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6">
        {/* Chat Area */}
        <Card className="shadow-lg">
          <CardContent className="p-0">
            <ScrollArea className="h-[600px] p-6" ref={scrollRef}>
              <div className="space-y-4">
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                  <div
                    className={`max-w-full rounded-lg p-4 ${
                        message.role === "user"
                          ? "bg-brand-blue text-white"
                          : "bg-muted"
                      }`}
                    >
                      {typeof message.content === 'string' ? (
                        <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                      ) : (
                        <div className="text-sm">{message.content}</div>
                      )}
                      <p className="text-xs mt-2 opacity-70">
                        {message.timestamp.toLocaleTimeString()}
                      </p>
                    </div>
                  </div>
                ))}
                {isTyping && (
                  <div className="flex justify-start">
                    <div className="bg-muted rounded-lg p-4">
                      <div className="flex space-x-2">
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </ScrollArea>

            {/* Input Area */}
            <div className="border-t p-4">
              {showSuggestion && (
                <div className="mb-3 flex flex-wrap gap-2">
                  <Badge 
                    variant="outline" 
                    className="cursor-pointer hover:bg-brand-blue hover:text-white transition-colors"
                    onClick={() => handleSuggestionClick('355481530062')}
                  >
                    Try: 355481530062
                  </Badge>
                  <Badge 
                    variant="outline" 
                    className="cursor-pointer hover:bg-brand-blue hover:text-white transition-colors"
                    onClick={() => handleSuggestionClick('TXN001')}
                  >
                    Try: TXN001
                  </Badge>
                </div>
              )}
              <div className="flex gap-2">
                <Input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Enter RRN (12 digits) or Transaction ID..."
                  className="flex-1"
                  disabled={isTyping}
                />
                <Button
                  onClick={handleSend}
                  disabled={isTyping || !input.trim()}
                  className="bg-brand-blue hover:bg-brand-mid"
                >
                  <Send className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Instructions removed - using FAQs instead */}
        {false && (
          <Card className="shadow-lg">
            <CardContent className="pt-6 space-y-6">
              <div>
                <h3 className="font-semibold mb-3 flex items-center gap-2">
                  <Search className="w-4 h-4" />
                  How to Search
                </h3>
                <div className="space-y-2 text-sm text-muted-foreground">
                  <p>• Enter a 12-digit RRN number</p>
                  <p>• Or enter a Transaction ID</p>
                  <p>• Press Enter or click Send</p>
                </div>
              </div>

              <div className="border-t pt-4">
                <h3 className="font-semibold mb-3">Status Indicators</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center gap-2">
                    <Badge className="bg-green-500">MATCHED</Badge>
                    <span className="text-xs text-muted-foreground">All systems agree</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge className="bg-yellow-500">PARTIAL</Badge>
                    <span className="text-xs text-muted-foreground">2 systems match</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge className="bg-orange-500">HANGING</Badge>
                    <span className="text-xs text-muted-foreground">Only 1 system</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge className="bg-red-500">MISMATCH</Badge>
                    <span className="text-xs text-muted-foreground">Data conflict</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}