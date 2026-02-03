import { ReactNode } from "react";

interface TableProps {
    headers: string[];
    data: ReactNode[][];
    className?: string;
    emptyMessage?: string;
}

export function Table({ headers, data, className = "", emptyMessage = "No data available" }: TableProps) {
    return (
        <div className={`w-full overflow-hidden border border-border rounded-lg ${className}`}>
            <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                    <thead className="text-xs text-muted-foreground uppercase bg-foreground-5 border-b border-border">
                        <tr>
                            {headers.map((header, i) => (
                                <th key={i} className="px-4 py-3 font-medium whitespace-nowrap">
                                    {header}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-border bg-background">
                        {data.length > 0 ? (
                            data.map((row, rowIndex) => (
                                <tr key={rowIndex} className="hover:bg-foreground-5/30 transition-colors">
                                    {row.map((cell, cellIndex) => (
                                        <td key={cellIndex} className="px-4 py-2 whitespace-nowrap text-foreground">
                                            {cell}
                                        </td>
                                    ))}
                                </tr>
                            ))
                        ) : (
                            <tr>
                                <td colSpan={headers.length} className="px-4 py-8 text-center text-muted-foreground">
                                    {emptyMessage}
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
