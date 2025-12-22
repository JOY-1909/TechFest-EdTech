import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { FileText, PenLine, Upload, ArrowRight } from "lucide-react";

export default function ProfileSetupChoice() {
    const navigate = useNavigate();

    const handleAutofillWithResume = () => {
        // Navigate to MultiStepForm with autofill mode
        navigate("/complete-profile", { state: { autofill: true } });
    };

    const handleManualFill = () => {
        // Navigate to MultiStepForm in regular mode (no resume upload shown)
        navigate("/complete-profile", { state: { autofill: false } });
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-blue-50 to-white px-4 py-12">
            <div className="max-w-4xl w-full space-y-8">
                {/* Header */}
                <div className="text-center space-y-4">
                    <h1 className="text-3xl font-bold text-gray-900">
                        Complete Your Profile
                    </h1>
                    <p className="text-gray-600 max-w-lg mx-auto">
                        Choose how you'd like to set up your profile. You can upload your resume for automatic extraction or fill in the details manually.
                    </p>
                </div>

                {/* Options Grid */}
                <div className="grid md:grid-cols-2 gap-6">
                    {/* Option A: Autofill with Resume */}
                    <Card className="relative border-2 hover:border-blue-500 hover:shadow-lg transition-all cursor-pointer group"
                        onClick={handleAutofillWithResume}
                    >
                        <div className="absolute top-4 right-4">
                            <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full font-medium">
                                Recommended
                            </span>
                        </div>
                        <CardHeader className="pb-4">
                            <div className="w-16 h-16 rounded-full bg-blue-100 flex items-center justify-center mb-4 group-hover:bg-blue-200 transition-colors">
                                <Upload className="w-8 h-8 text-blue-600" />
                            </div>
                            <CardTitle className="text-xl">Autofill with Resume</CardTitle>
                            <CardDescription className="text-gray-500">
                                Upload your PDF resume and we'll extract your details automatically
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <ul className="space-y-2 text-sm text-gray-600">
                                <li className="flex items-center gap-2">
                                    <FileText className="w-4 h-4 text-blue-500" />
                                    Upload PDF resume
                                </li>
                                <li className="flex items-center gap-2">
                                    <FileText className="w-4 h-4 text-blue-500" />
                                    Auto-extract education, experience, skills
                                </li>
                                <li className="flex items-center gap-2">
                                    <FileText className="w-4 h-4 text-blue-500" />
                                    Review and edit before saving
                                </li>
                            </ul>
                            <Button className="w-full mt-4 group-hover:bg-blue-700">
                                Upload Resume
                                <ArrowRight className="w-4 h-4 ml-2" />
                            </Button>
                        </CardContent>
                    </Card>

                    {/* Option B: Manual Fill */}
                    <Card className="relative border-2 hover:border-gray-400 hover:shadow-lg transition-all cursor-pointer group"
                        onClick={handleManualFill}
                    >
                        <CardHeader className="pb-4">
                            <div className="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center mb-4 group-hover:bg-gray-200 transition-colors">
                                <PenLine className="w-8 h-8 text-gray-600" />
                            </div>
                            <CardTitle className="text-xl">Fill Details Manually</CardTitle>
                            <CardDescription className="text-gray-500">
                                Enter your information step by step using our guided form
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <ul className="space-y-2 text-sm text-gray-600">
                                <li className="flex items-center gap-2">
                                    <PenLine className="w-4 h-4 text-gray-500" />
                                    Step-by-step guided form
                                </li>
                                <li className="flex items-center gap-2">
                                    <PenLine className="w-4 h-4 text-gray-500" />
                                    Full control over every field
                                </li>
                                <li className="flex items-center gap-2">
                                    <PenLine className="w-4 h-4 text-gray-500" />
                                    Live resume preview as you type
                                </li>
                            </ul>
                            <Button variant="outline" className="w-full mt-4">
                                Start from Scratch
                                <ArrowRight className="w-4 h-4 ml-2" />
                            </Button>
                        </CardContent>
                    </Card>
                </div>

                {/* Footer Note */}
                <p className="text-center text-sm text-gray-500">
                    Don't worry — you can always edit your profile later and upload a resume anytime.
                </p>
            </div>
        </div>
    );
}
