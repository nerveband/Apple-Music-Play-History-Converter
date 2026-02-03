interface ProgressProps {
    value: number; // 0 to 100
    max?: number;
    className?: string;
    showLabel?: boolean;
    color?: "default" | "success" | "warning";
}

export function Progress({
    value,
    max = 100,
    className = "",
    showLabel = false,
    color = "default",
}: ProgressProps) {
    const percentage = Math.min(Math.max((value / max) * 100, 0), 100);

    const colors = {
        default: "from-accent to-accent/80",
        success: "from-success to-success/80",
        warning: "from-warning to-warning/80",
    };

    return (
        <div className={`w-full ${className}`}>
            <div className="flex justify-between text-xs mb-1">
                {showLabel && <span>{percentage.toFixed(0)}%</span>}
            </div>
            <div className="h-2 bg-foreground-10 rounded-full overflow-hidden">
                <div
                    className={`h-full bg-gradient-to-r ${colors[color]} transition-all duration-300 rounded-full`}
                    style={{ width: `${percentage}%` }}
                />
            </div>
        </div>
    );
}
