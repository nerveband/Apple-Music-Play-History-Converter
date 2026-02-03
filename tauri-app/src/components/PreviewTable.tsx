import { useEffect, useState } from "react";
import { Table } from "./ui/Table";
import { getCsvPreview } from "../lib/commands";
import { ChartBar, Spinner } from "@phosphor-icons/react";

interface PreviewTableProps {
    filePath: string | null;
}

export function PreviewTable({ filePath }: PreviewTableProps) {
    const [data, setData] = useState<string[][]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (filePath) {
            loadPreview(filePath);
        } else {
            setData([]);
        }
    }, [filePath]);

    const loadPreview = async (path: string) => {
        setLoading(true);
        try {
            const rows = await getCsvPreview(path);
            setData(rows);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    if (!filePath) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-muted-foreground p-8">
                <ChartBar size={48} className="mb-4 opacity-20" />
                <p>Select a CSV file to see a preview of the tracks</p>
            </div>
        );
    }

    if (loading) {
        return (
            <div className="h-full flex items-center justify-center">
                <Spinner size={32} className="animate-spin text-accent" />
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col">
            <div className="p-2 bg-foreground-5/30 border-b border-border text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Preview: First {data.length} rows
            </div>
            <div className="flex-1 overflow-auto bg-background">
                <Table
                    headers={["Artist", "Title", "Album", "Date", "Duration"]}
                    data={data}
                    className="rounded-none border-0"
                    emptyMessage="No preview data available"
                />
            </div>
        </div>
    );
}
