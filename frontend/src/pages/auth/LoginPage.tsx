import { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Terminal, User, Lock, LogIn, AlertCircle } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { authApi } from '@/api/auth';
import { useAuthStore } from '@/store/useAuthStore';
import { useNavigate } from 'react-router-dom';

const loginSchema = z.object({
  loginId: z.string().min(1, '아이디를 입력해주세요.'),
  password: z.string().min(1, '비밀번호를 입력해주세요.'),
});

type LoginFormData = z.infer<typeof loginSchema>;

interface LoginFormProps {
  role: 'USER' | 'ADMIN';
  isLoading: boolean;
  onSubmit: (data: LoginFormData, role: 'USER' | 'ADMIN') => void;
  errorMsg: string | null;
}

const LoginForm = ({ role, isLoading, onSubmit, errorMsg }: LoginFormProps) => {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  return (
    <form onSubmit={handleSubmit((data) => onSubmit(data, role))} className="flex flex-col gap-6">
      <div className="flex flex-col gap-4">
        {/* ID Input */}
        <div className="relative">
          <label className="absolute -top-2 left-2 bg-[#0d1c2d] px-1 text-[#c1c7d3] text-[12px] font-medium tracking-[0.6px] z-10">
            아이디
          </label>
          <div className={`bg-[#010f1f] border ${errors.loginId ? 'border-red-500' : 'border-[rgba(65,71,81,0.3)]'} rounded-[4px] h-[50px] flex items-center px-4 mt-2 relative focus-within:border-[#60a5fa] focus-within:ring-1 focus-within:ring-[#60a5fa]/50 transition-colors`}>
            <User className={`w-4 h-4 mr-3 ${errors.loginId ? 'text-red-500' : 'text-[#8b919d]'}`} />
            <input
              type="text"
              placeholder="ID"
              className="bg-transparent border-none outline-none text-[#8b919d] text-[16px] w-full"
              {...register('loginId')}
            />
          </div>
          {errors.loginId && (
            <span className="text-red-500 text-[12px] mt-1 ml-1 block">{errors.loginId.message}</span>
          )}
        </div>

        {/* Password Input */}
        <div className="relative">
          <label className="absolute -top-2 left-2 bg-[#0d1c2d] px-1 text-[#c1c7d3] text-[12px] font-medium tracking-[0.6px] z-10">
            비밀번호
          </label>
          <div className={`bg-[#010f1f] border ${errors.password ? 'border-red-500' : 'border-[rgba(65,71,81,0.3)]'} rounded-[4px] h-[50px] flex items-center px-4 mt-2 relative focus-within:border-[#60a5fa] focus-within:ring-1 focus-within:ring-[#60a5fa]/50 transition-colors`}>
            <Lock className={`w-4 h-4 mr-3 ${errors.password ? 'text-red-500' : 'text-[#8b919d]'}`} />
            <input
              type="password"
              placeholder="Password"
              className="bg-transparent border-none outline-none text-[#8b919d] text-[16px] w-full"
              {...register('password')}
            />
          </div>
          {errors.password && (
            <span className="text-red-500 text-[12px] mt-1 ml-1 block">{errors.password.message}</span>
          )}
        </div>
        
        {/* Error Message */}
        {errorMsg && (
          <div className="flex items-center gap-2 text-red-400 bg-red-400/10 p-3 rounded-[4px] text-[13px] border border-red-400/20">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <p>{errorMsg}</p>
          </div>
        )}
      </div>

      {/* Action Button */}
      <button
        type="submit"
        disabled={isLoading}
        className="w-full bg-[#60a5fa] hover:bg-[#3b82f6] text-[#003a6b] font-medium text-[18px] rounded-[4px] h-[50px] flex items-center justify-center gap-2 transition-colors disabled:opacity-70"
      >
        {isLoading ? '로그인 중...' : '로그인'}
        {!isLoading && <LogIn className="w-4 h-4" />}
      </button>
    </form>
  );
};

export default function LoginPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const login = useAuthStore((state) => state.login);
  const navigate = useNavigate();

  const handleLogin = async (data: LoginFormData, role: 'USER' | 'ADMIN') => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      // In a real scenario, you might send the role as well if the API supports it,
      // or the API determines the role based on the credentials.
      const res = await authApi.login(data);
      
      // 권한 검증: 관리자 탭에서 일반 유저 로그인 시도 시
      if (role === 'ADMIN' && res.systemRole === 'USER') {
        setErrorMsg('해당 계정은 관리자 권한이 없습니다. 사용자 탭을 이용해주세요.');
        return;
      }

      // 권한 검증: 사용자 탭에서 관리자 로그인 시도 시
      if (role === 'USER' && (res.systemRole === 'SUPER_ADMIN' || res.systemRole === 'PROJECT_ADMIN')) {
        setErrorMsg('해당 계정은 관리자입니다. 관리자 탭을 이용해주세요.');
        return;
      }

      // Use the response data to populate auth store
      login(res.accessToken, {
        id: res.userId,
        name: res.name,
        systemRole: res.systemRole,
      });

      // Redirect to main page after successful login
      navigate('/');
    } catch (err: any) {
      console.error('Login Error:', err);
      if (err.response?.status === 401) {
        setErrorMsg('아이디 또는 비밀번호가 올바르지 않습니다.');
      } else {
        setErrorMsg('서버와 통신 중 문제가 발생했습니다. 잠시 후 다시 시도해주세요.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full flex flex-col items-center">
      {/* Brand Identity Section */}
      <div className="mb-8 flex flex-col items-center">
        <div className="w-[58px] h-[50px] relative flex items-center justify-center bg-[#0F223A] border border-[#254670] rounded-xl mb-4 shadow-[0_0_20px_rgba(37,99,235,0.2)]">
          <Terminal className="w-7 h-7 text-[#60a5fa]" />
        </div>
        <h1 className="font-['Space_Grotesk'] font-bold text-[#d4e4fa] text-[32px] tracking-[-1.6px] leading-tight">
          Theseus
        </h1>
        <p className="font-semibold text-[#c1c7d3] text-[12px] tracking-[1.2px] uppercase mt-1">
          AI LAB SYSTEM
        </p>
      </div>

      {/* Login Card */}
      <div className="w-full max-w-[420px] backdrop-blur-[12px] bg-[#0d1c2d] border border-[rgba(65,71,81,0.2)] rounded-[8px] shadow-[0px_20px_50px_0px_rgba(0,0,0,0.5)] overflow-hidden relative">
        
        {/* Decorative Corner Accents */}
        <div className="absolute top-0 left-0 w-[48px] h-[48px] border-t border-l border-[rgba(65,71,81,0.3)] pointer-events-none" />
        <div className="absolute top-0 right-0 w-[48px] h-[48px] border-t border-r border-[rgba(65,71,81,0.3)] pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-[48px] h-[48px] border-b border-l border-[rgba(65,71,81,0.3)] pointer-events-none" />
        <div className="absolute bottom-0 right-0 w-[48px] h-[48px] border-b border-r border-[rgba(65,71,81,0.3)] pointer-events-none" />

        <Tabs defaultValue="user" className="w-full">
          {/* Tabs */}
          <TabsList className="w-full bg-transparent border-b border-[rgba(65,71,81,0.2)] rounded-none h-auto p-0 flex">
            <TabsTrigger 
              value="user" 
              className="flex-1 rounded-none data-[state=active]:bg-[rgba(28,43,60,0.4)] data-[state=active]:border-b-2 data-[state=active]:border-[#60a5fa] data-[state=active]:text-[#60a5fa] text-[#c1c7d3] h-[58px] text-[18px] font-medium transition-none data-[state=active]:shadow-none"
            >
              사용자
            </TabsTrigger>
            <TabsTrigger 
              value="admin" 
              className="flex-1 rounded-none data-[state=active]:bg-[rgba(28,43,60,0.4)] data-[state=active]:border-b-2 data-[state=active]:border-[#60a5fa] data-[state=active]:text-[#60a5fa] text-[#c1c7d3] h-[58px] text-[18px] font-medium transition-none data-[state=active]:shadow-none"
            >
              관리자
            </TabsTrigger>
          </TabsList>

          <TabsContent value="user" className="p-6 m-0 focus-visible:outline-none focus-visible:ring-0">
            <LoginForm role="USER" isLoading={isLoading} onSubmit={handleLogin} errorMsg={errorMsg} />
          </TabsContent>

          <TabsContent value="admin" className="p-6 m-0 focus-visible:outline-none focus-visible:ring-0">
            <LoginForm role="ADMIN" isLoading={isLoading} onSubmit={handleLogin} errorMsg={errorMsg} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
