import { InputHTMLAttributes, forwardRef } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
    label?: string;
    error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
    ({ className = "", label, error, ...props }, ref) => {
        return (
            <div className="w-full">
                {label && (
                    <label className="block text-sm font-medium text-muted-foreground mb-1">
                        {label}
                    </label>
                )}
                <input
                    className={`w-full px-3 py-2 rounded-lg border bg-background text-foreground transition-all
            focus:outline-none focus:ring-2 focus:ring-accent/50
            placeholder:text-muted-foreground/50
            ${error ? "border-destructive focus:ring-destructive/50" : "border-border focus:border-accent"}
            ${className}`}
                    ref={ref}
                    {...props}
                />
                {error && <p className="mt-1 text-xs text-destructive">{error}</p>}
            </div>
        );
    }
);

Input.displayName = "Input";
