import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import { Button } from "../components/ui/button";
import { CheckCircle, Sparkles } from "lucide-react";

interface WelcomeDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function WelcomeDialog({ isOpen, onClose }: WelcomeDialogProps) {
  const [showContent, setShowContent] = useState(false);

  useEffect(() => {
    if (isOpen) {
      // Delay showing content for smooth animation
      const timer = setTimeout(() => setShowContent(true), 300);
      return () => clearTimeout(timer);
    } else {
      setShowContent(false);
    }
  }, [isOpen]);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md border-0 shadow-2xl">
        <div className="text-center space-y-6">
          {/* Animated Icon */}
          <div className="flex justify-center">
            <div className="relative">
              <div className="w-20 h-20 bg-gradient-to-br from-brand-blue to-brand-sky rounded-full flex items-center justify-center shadow-lg">
                <Sparkles className="w-10 h-10 text-white" />
              </div>
              <div className="absolute -top-1 -right-1 w-6 h-6 bg-green-500 rounded-full flex items-center justify-center">
                <CheckCircle className="w-4 h-4 text-white" />
              </div>
            </div>
          </div>

          {/* Welcome Content */}
          <div className={`space-y-4 transition-all duration-500 ${showContent ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
            <DialogHeader>
              <DialogTitle className="text-2xl font-bold text-brand-dark">
                Welcome to UPI Recon!
              </DialogTitle>
              <DialogDescription className="text-base text-muted-foreground">
                Your unified platform for UPI transaction reconciliation and analysis
              </DialogDescription>
            </DialogHeader>

            {/* Features List */}
            <div className="space-y-3 text-left bg-brand-light/50 rounded-lg p-4">
              <h4 className="font-semibold text-brand-dark">What you can do:</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-green-600 flex-shrink-0" />
                  Upload and process transaction files
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-green-600 flex-shrink-0" />
                  Perform automated reconciliation
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-green-600 flex-shrink-0" />
                  View detailed reports and analytics
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-green-600 flex-shrink-0" />
                  Manage rollbacks and corrections
                </li>
              </ul>
            </div>

            {/* Action Button */}
            <Button
              onClick={onClose}
              className="w-full bg-brand-blue hover:bg-brand-mid text-white font-medium py-3"
            >
              Get Started
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
