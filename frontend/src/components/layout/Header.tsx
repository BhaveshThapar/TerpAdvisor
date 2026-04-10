interface HeaderProps {
  userName?: string;
}

export default function Header({ userName = "Terp User" }: HeaderProps) {
  return (
    <header className="flex h-14 items-center justify-between border-b border-gray-200 bg-white px-6 shadow-sm">
      {/* Logo / title */}
      <div className="flex items-center gap-2">
        <span className="text-xl font-bold" style={{ color: "#e21833" }}>
          TerpAdvisor
        </span>
        <span
          className="hidden rounded-full px-2 py-0.5 text-[10px] font-semibold text-gray-700 sm:inline-block"
          style={{ backgroundColor: "#ffd200" }}
        >
          BETA
        </span>
      </div>

      {/* User area */}
      <div className="flex items-center gap-3">
        <span className="text-sm text-gray-600">{userName}</span>
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gray-200 text-sm font-semibold text-gray-600">
          {userName.charAt(0).toUpperCase()}
        </div>
      </div>
    </header>
  );
}
