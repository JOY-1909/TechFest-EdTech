import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { Upload, Loader2, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";

interface ParsedResume {
    profile: {
        name: string;
        email: string;
        phone: string;
        location: string;
        url: string;
        summary: string;
    };
    educations: Array<{
        school: string;
        degree: string;
        date: string;
        gpa: string;
        descriptions: string[];
    }>;
    workExperiences: Array<{
        company: string;
        jobTitle: string;
        date: string;
        descriptions: string[];
    }>;
    projects: Array<{
        project: string;
        date: string;
        descriptions: string[];
    }>;
    skills: {
        featuredSkills: Array<{ skill: string; rating: number }>;
        descriptions: string[];
    };
}

type UploadState = "idle" | "uploading" | "parsing" | "success" | "error";

interface ResumeUploadButtonProps {
    onParseSuccess: (resume: ParsedResume) => void;
    onParseError?: (error: string) => void;
    className?: string;
    variant?: "default" | "compact";
}

export function ResumeUploadButton({
    onParseSuccess,
    onParseError,
    className = "",
    variant = "default",
}: ResumeUploadButtonProps) {
    const { toast } = useToast();
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [uploadState, setUploadState] = useState<UploadState>("idle");
    const [fileName, setFileName] = useState<string>("");

    const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        // Validate file type
        if (!file.name.toLowerCase().endsWith(".pdf")) {
            toast({
                title: "Invalid file type",
                description: "Please upload a PDF file.",
                variant: "destructive",
            });
            return;
        }

        // Validate file size (10MB max)
        if (file.size > 10 * 1024 * 1024) {
            toast({
                title: "File too large",
                description: "Please upload a file smaller than 10MB.",
                variant: "destructive",
            });
            return;
        }

        setFileName(file.name);
        setUploadState("uploading");

        try {
            // Create form data for upload
            const formData = new FormData();
            formData.append("file", file);

            // Update state to parsing
            setUploadState("parsing");

            // Call the parse-resume API
            const response = await fetch("http://localhost:3000/api/parse-resume", {
                method: "POST",
                body: formData,
            });

            const result = await response.json();

            if (!response.ok || !result.success) {
                throw new Error(result.error || "Failed to parse resume");
            }

            setUploadState("success");
            toast({
                title: "Resume parsed successfully! 🎉",
                description: "Your resume data has been extracted. Review the form below.",
            });

            // Call success callback with parsed data
            onParseSuccess(result.resume);

        } catch (error) {
            setUploadState("error");
            const errorMessage = error instanceof Error ? error.message : "Failed to parse resume";

            toast({
                title: "Parsing failed",
                description: errorMessage,
                variant: "destructive",
            });

            if (onParseError) {
                onParseError(errorMessage);
            }
        }

        // Reset file input
        if (fileInputRef.current) {
            fileInputRef.current.value = "";
        }
    };

    const handleButtonClick = () => {
        fileInputRef.current?.click();
    };

    const handleRetry = () => {
        setUploadState("idle");
        setFileName("");
        fileInputRef.current?.click();
    };

    const getButtonContent = () => {
        switch (uploadState) {
            case "uploading":
                return (
                    <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Uploading...
                    </>
                );
            case "parsing":
                return (
                    <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Parsing resume...
                    </>
                );
            case "success":
                return (
                    <>
                        <CheckCircle2 className="w-4 h-4 text-green-500" />
                        Parsed: {fileName}
                    </>
                );
            case "error":
                return (
                    <>
                        <AlertCircle className="w-4 h-4 text-red-500" />
                        Failed - Click to retry
                    </>
                );
            default:
                return (
                    <>
                        <Upload className="w-4 h-4" />
                        {variant === "compact" ? "Upload Resume" : "📄 Upload your resume for parsing"}
                    </>
                );
        }
    };

    const isDisabled = uploadState === "uploading" || uploadState === "parsing";

    if (variant === "compact") {
        return (
            <div className={className}>
                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf"
                    className="hidden"
                    onChange={handleFileSelect}
                    disabled={isDisabled}
                />
                <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={uploadState === "error" ? handleRetry : handleButtonClick}
                    disabled={isDisabled}
                    className="gap-2"
                >
                    {getButtonContent()}
                </Button>
            </div>
        );
    }

    return (
        <div className={`border-2 border-dashed border-blue-200 rounded-lg p-6 bg-blue-50/50 hover:bg-blue-50 transition-colors ${className}`}>
            <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={handleFileSelect}
                disabled={isDisabled}
            />

            <div className="flex flex-col items-center gap-4">
                <div className="flex items-center gap-3">
                    {uploadState === "success" ? (
                        <CheckCircle2 className="w-8 h-8 text-green-500" />
                    ) : uploadState === "error" ? (
                        <AlertCircle className="w-8 h-8 text-red-500" />
                    ) : (
                        <Upload className="w-8 h-8 text-blue-500" />
                    )}

                    <div className="text-left">
                        <p className="font-medium text-gray-900">
                            {uploadState === "success"
                                ? "Resume parsed successfully!"
                                : uploadState === "error"
                                    ? "Failed to parse resume"
                                    : "Upload your resume"}
                        </p>
                        <p className="text-sm text-gray-500">
                            {uploadState === "success"
                                ? fileName
                                : uploadState === "error"
                                    ? "Click below to try again"
                                    : "PDF files only, max 10MB"}
                        </p>
                    </div>
                </div>

                <div className="flex gap-2">
                    <Button
                        type="button"
                        onClick={uploadState === "error" ? handleRetry : handleButtonClick}
                        disabled={isDisabled}
                        className="gap-2"
                    >
                        {getButtonContent()}
                    </Button>

                    {uploadState === "success" && (
                        <Button
                            type="button"
                            variant="outline"
                            onClick={handleRetry}
                            className="gap-2"
                        >
                            <RefreshCw className="w-4 h-4" />
                            Upload Different Resume
                        </Button>
                    )}
                </div>
            </div>
        </div>
    );
}

export type { ParsedResume };
