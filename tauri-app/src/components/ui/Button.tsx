import { ReactNode, ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: "primary" | "secondary" | "ghost" | "destructive" | "outline";
    size?: "sm" | "md" | "lg";
    loading?: boolean;
    children: ReactNode;
    icon?: ReactNode;
}

export function Button({
    variant = "primary",
    size = "md",
    loading = false,
    className = "",
    children,
    icon,
    disabled,
    ...props
}: ButtonProps) {
    const baseStyles = "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed";

    const variants = {
        primary: "bg-accent text-white hover:bg-accent/90 focus:ring-accent",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80 focus:ring-secondary",
        ghost: "bg-transparent hover:bg-foreground-5 text-foreground focus:ring-foreground-20",
        destructive: "bg-destructive/10 text-destructive hover:bg-destructive/20 focus:ring-destructive",
        outline: "border border-border bg-transparent hover:bg-foreground-5 focus:ring-foreground-20",
    };

    const sizes = {
        sm: "px-3 py-1.5 text-xs",
        md: "px-4 py-2 text-sm",
        lg: "px-6 py-3 text-base",
    };

    return (
        <button
            className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${className}`}
            disabled={disabled || loading}
            {...props}
        >
            {loading && <span className="animate-spin">⏳</span>}
            {!loading && icon}
            {children}
        </button>
    );
}
