import { ReactNode, useState, useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { cn } from "../lib/utils";
import {
  LayoutDashboard,
  Upload,
  Eye,
  BarChart3,
  AlertCircle,
  GitMerge,
  PlayCircle,
  RotateCcw,
  HelpCircle,
  FileText,
  PanelLeftClose,
  PanelLeft,
  LogOut,
  Sparkles,
  Shield,
  EyeOff,
  UserCheck,
  MessageSquare,
  Scale,
  RefreshCcw,
  TrendingUp
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "../components/ui/tooltip";
import nstechxLogo from "../assets/nstechxbg.png";
import verifAiLogo from "../assets/verif_ai.png";

interface LayoutProps {
  children: ReactNode;
}

interface MenuItem {
  path: string;
  label: string;
  icon: any;
  disabled?: boolean;
  hidden?: boolean;
}

const menuItems: MenuItem[] = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard },
  { path: "/file-upload", label: "File Upload", icon: Upload },
  { path: "/view-status", label: "View Upload Status", icon: Eye },
  { path: "/recon", label: "Run Reconciliation", icon: BarChart3 },
  { path: "/unmatched", label: "Unmatched Dashboard", icon: AlertCircle },
  { path: "/force-match", label: "Force - Match", icon: GitMerge },
  { path: "/auto-match", label: "Auto-Match", icon: PlayCircle, disabled: true, hidden: true },
  { path: "/rollback", label: "Roll-Back", icon: RotateCcw },
  { path: "/cycle-skip", label: "NPCI Cycle Skip", icon: RefreshCcw },
  { path: "/income-expense", label: "Income & Expense", icon: TrendingUp },
  { path: "/enquiry", label: "Ask Verif.AI", icon: MessageSquare },
  { path: "/reports", label: "Reports", icon: FileText },
  { path: "/ai-showcase", label: "AI Showcase", icon: Sparkles },
  { path: "/blockchain", label: "Blockchain Audit", icon: Shield },
];

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout, user } = useAuth();
  const [isCollapsed, setIsCollapsed] = useState(true); // Start collapsed

  // Scroll to top on location change
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);

  // Load saved state from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("sidebar-collapsed");
    if (saved !== null) {
      setIsCollapsed(saved === "true");
    }
  }, []);

  // Save state to localStorage
  const toggleSidebar = () => {
    const newState = !isCollapsed;
    setIsCollapsed(newState);
    localStorage.setItem("sidebar-collapsed", String(newState));
  };

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="flex min-h-screen w-full bg-background no-select">
      {/* Sidebar */}
      <aside 
        className={cn(
          "bg-sidebar border-r border-sidebar-border shadow-xl transition-all duration-300 ease-in-out flex flex-col no-select",
          isCollapsed ? "w-16" : "w-64"
        )}
      >
        <div className="p-3 flex-1 flex flex-col">
          {/* Logo Section */}
          <div className={cn(
            "mb-2 pb-3 border-b border-sidebar-border flex justify-center",
            isCollapsed ? "px-2" : "px-4"
          )}>
            <img 
              src={nstechxLogo} 
              alt="NStechX" 
              className={cn(
                "object-contain rounded",
                isCollapsed ? "h-14 w-14" : "h-20 w-20"
              )}
            />
          </div>

          {/* Toggle Button */}
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleSidebar}
            className="mb-4 self-end text-sidebar-foreground hover:bg-sidebar-accent"
          >
            {isCollapsed ? (
              <PanelLeft className="w-5 h-5" />
            ) : (
              <PanelLeftClose className="w-5 h-5" />
            )}
          </Button>

          {/* User Info */}
          <div className={cn(
            "flex items-center gap-3 mb-6 pb-4 border-b border-sidebar-border",
            isCollapsed && "justify-center"
          )}>
            <div className="w-10 h-10 rounded-full bg-sidebar-primary flex items-center justify-center flex-shrink-0">
              <span className="text-sidebar-primary-foreground font-semibold">
                {user?.username?.[0]?.toUpperCase() || 'U'}
              </span>
            </div>
            {!isCollapsed && (
              <div className="text-sidebar-foreground overflow-hidden">
                <p className="font-medium text-sm truncate">{user?.username || 'User'}</p>
                <p className="text-xs text-sidebar-foreground/70">{user?.role || 'Role'}</p>
              </div>
            )}
          </div>

          {/* Navigation Menu */}
          <nav className="space-y-1 flex-1">
            {menuItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;

              // Skip hidden items
              if (item.hidden) {
                return null;
              }

              // Hide certain menu items for Maker-only users
              if (user?.role === 'Maker' && (item.label === 'Force - Match' || item.label === 'Roll-Back')) {
                return null;
              }

              const linkContent = (
                <Link
                  to={item.path}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all",
                    isActive
                      ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-lg"
                      : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                    isCollapsed && "justify-center px-2",
                    item.disabled && "opacity-50 cursor-not-allowed pointer-events-none"
                  )}
                >
                  <Icon className="w-5 h-5 flex-shrink-0" />
                  {!isCollapsed && <span className="truncate">{item.label}</span>}
                </Link>
              );

              if (isCollapsed) {
                return (
                  <Tooltip key={item.path} delayDuration={0}>
                    <TooltipTrigger asChild>
                      {linkContent}
                    </TooltipTrigger>
                    <TooltipContent side="right" className="bg-sidebar text-sidebar-foreground border-sidebar-border">
                      {item.label}
                    </TooltipContent>
                  </Tooltip>
                );
              }

              return <div key={item.path}>{linkContent}</div>;
            })}
          </nav>

          {/* Logout Button */}
          <div className="pt-4 border-t border-sidebar-border">
            <Button
              onClick={handleLogout}
              variant="ghost"
              size={isCollapsed ? "icon" : "default"}
              className="w-full text-sidebar-foreground/70 hover:bg-destructive/20 hover:text-destructive justify-start"
            >
              <LogOut className="w-5 h-5 flex-shrink-0" />
              {!isCollapsed && <span className="ml-3">Logout</span>}
            </Button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto flex flex-col no-select">
        {/* Top Bar with verif.ai Logo */}
        <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-end no-select">
          <img
            src={verifAiLogo}
            alt="verif.ai"
            className="h-20 object-contain no-select"
            draggable={false}
          />
        </div>
        <div key={location.pathname} className="flex-1 overflow-auto">
          {children}
        </div>
      </main>
    </div>
  );
}
