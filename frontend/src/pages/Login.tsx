import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2 } from "lucide-react";
import verifAiLogo from "../assets/verif_ai.png";
import nstechxLogo from "../assets/nstechx.jpeg";

const Login = () => {
  const navigate = useNavigate();
  const { login, isAuthenticated, loading: authLoading } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated && !authLoading) {
      navigate("/");
    }
  }, [isAuthenticated, authLoading, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          <p className="text-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 p-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl shadow-xl p-10 border border-gray-100">
          {/* verif.ai Logo - Top Center */}
          <div className="flex justify-center mb-6">
            <img 
              src={verifAiLogo} 
              alt="verif.ai" 
              className="h-40 object-contain"
            />
          </div>

          {/* Heading */}
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold text-gray-900 mb-2">Login to Verif.AI</h1>
            <p className="text-gray-600 text-sm">Enter your credentials to access the system</p>
          </div>

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-2">
                Username
              </label>
              <Input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your username"
                disabled={loading}
                className="w-full h-11 px-4 bg-white border border-gray-300 focus:border-primary focus:ring-primary rounded-lg"
                required
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
                Password
              </label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                disabled={loading}
                className="w-full h-11 px-4 bg-white border border-gray-300 focus:border-primary focus:ring-primary rounded-lg"
                required
              />
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="w-full h-11 bg-primary hover:bg-primary/90 text-white font-medium rounded-lg transition-colors mt-6"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Logging in...
                </>
              ) : (
                "Login"
              )}
            </Button>
          </form>

          {/* Product by NStechX */}
          <div className="mt-8 pt-6 border-t border-gray-200">
            <div className="flex items-center justify-center gap-3 text-xl text-gray-600">
              <span>Product by</span>
              <img 
                src={nstechxLogo} 
                alt="NStechX" 
              className="h-20 object-contain"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;