import type { FormData, EducationItem, ExperienceItem, ProjectItem, SkillItem, PortfolioItem } from "@/pages/MultiStepForm";
import type { ParsedResume } from "@/components/ui/ResumeUploadButton";

/**
 * Maps OpenResume parsed resume data to MultiStepForm FormData format.
 * Handles all sections: profile, education, work experience, projects, and skills.
 * Preserves all URLs and handles missing/partial data gracefully.
 */
export function mapParsedResumeToFormData(parsedResume: ParsedResume): Partial<FormData> {
    const { profile, educations, workExperiences, projects, skills } = parsedResume;

    // Parse name into first and last name
    const nameParts = (profile.name || "").trim().split(/\s+/);
    const firstName = nameParts[0] || "";
    const lastName = nameParts.slice(1).join(" ") || "";

    // Parse URL to identify LinkedIn, GitHub, or Portfolio
    let linkedin = "";
    let portfolioItems: Partial<PortfolioItem>[] = [];

    if (profile.url) {
        const urlLower = profile.url.toLowerCase();
        if (urlLower.includes("linkedin.com")) {
            linkedin = profile.url;
        } else if (urlLower.includes("github.com")) {
            // Add GitHub as a portfolio item
            portfolioItems.push({
                id: 1,
                title: "GitHub",
                link: profile.url,
                description: "",
            });
        } else {
            // Any other URL goes to portfolio
            portfolioItems.push({
                id: 1,
                title: "Portfolio",
                link: profile.url,
                description: "",
            });
        }
    }

    // Map educations
    const mappedEducation: EducationItem[] = educations.map((edu, index) => {
        // Parse date string (e.g., "2018 - 2022" or "May 2022")
        const dateParts = (edu.date || "").split(/[-–—]/);
        const startYear = dateParts[0]?.trim().match(/\d{4}/)?.[0] || "";
        const endYear = dateParts[1]?.trim().match(/\d{4}/)?.[0] || dateParts[0]?.trim().match(/\d{4}/)?.[0] || "";

        // Parse degree and field of study
        const degreeAndField = edu.degree || "";
        let degree = degreeAndField;
        let fieldOfStudy = "";

        // Try to split degree from field (e.g., "B.S. in Computer Science")
        const inMatch = degreeAndField.match(/^(.+?)\s+in\s+(.+)$/i);
        if (inMatch) {
            degree = inMatch[1].trim();
            fieldOfStudy = inMatch[2].trim();
        }

        return {
            id: index + 1,
            institution: edu.school || "",
            degree,
            fieldOfStudy,
            startYear,
            endYear,
            score: edu.gpa || "",
        };
    });

    // Map work experiences
    const mappedExperience: ExperienceItem[] = workExperiences.map((exp, index) => {
        // Parse date string
        const dateParts = (exp.date || "").split(/[-–—]/);
        const startDate = dateParts[0]?.trim() || "";
        const endDate = dateParts[1]?.trim() || "Present";

        // Convert descriptions array to string
        const description = (exp.descriptions || []).join("\n• ");

        return {
            id: index + 1,
            type: "Internship" as const,
            company: exp.company || "",
            role: exp.jobTitle || "",
            startDate,
            endDate,
            description: description ? `• ${description}` : "",
        };
    });

    // Map projects
    const mappedProjects: ProjectItem[] = projects.map((proj, index) => {
        const description = (proj.descriptions || []).join("\n• ");

        return {
            id: index + 1,
            title: proj.project || "",
            role: "",
            technologies: "",
            description: description ? `• ${description}` : "",
        };
    });

    // Map skills - combine featured skills and descriptions
    const mappedSkills: SkillItem[] = [];

    // Add featured skills
    if (skills.featuredSkills) {
        skills.featuredSkills.forEach((featuredSkill, index) => {
            if (featuredSkill.skill && featuredSkill.skill.trim()) {
                mappedSkills.push({
                    id: index + 1,
                    name: featuredSkill.skill.trim(),
                    level: featuredSkill.rating > 3 ? "Advanced" : featuredSkill.rating > 1 ? "Intermediate" : "Beginner",
                });
            }
        });
    }

    // Parse skill descriptions (often comma-separated lists)
    if (skills.descriptions) {
        skills.descriptions.forEach((desc) => {
            // Split by common delimiters
            const skillNames = desc.split(/[,;|•·]/);
            skillNames.forEach((skillName) => {
                const trimmed = skillName.trim();
                if (trimmed && trimmed.length > 1 && trimmed.length < 50) {
                    // Avoid duplicates
                    if (!mappedSkills.some(s => s.name.toLowerCase() === trimmed.toLowerCase())) {
                        mappedSkills.push({
                            id: mappedSkills.length + 1,
                            name: trimmed,
                            level: "Intermediate",
                        });
                    }
                }
            });
        });
    }

    return {
        firstName,
        lastName,
        email: profile.email || "",
        phone: profile.phone || "",
        address: profile.location || "",
        linkedin,
        careerObjective: profile.summary || "",
        education: mappedEducation.length > 0 ? mappedEducation : undefined,
        experience: mappedExperience.length > 0 ? mappedExperience : undefined,
        projects: mappedProjects.length > 0 ? mappedProjects : undefined,
        skills: mappedSkills.length > 0 ? mappedSkills : undefined,
        portfolio: portfolioItems.length > 0 ? portfolioItems as PortfolioItem[] : undefined,
    };
}

/**
 * Merges parsed resume data with existing form data.
 * For empty form fields: fills with parsed data
 * For non-empty form fields: preserves existing data (user can manually overwrite)
 */
export function mergeResumeDataWithFormData(
    existingData: FormData,
    parsedData: Partial<FormData>,
    overwriteNonEmpty = false
): FormData {
    const merged = { ...existingData };

    // Merge simple string fields
    const stringFields: (keyof FormData)[] = [
        "firstName", "lastName", "email", "phone", "address",
        "linkedin", "careerObjective", "languages"
    ];

    stringFields.forEach((field) => {
        const existingValue = existingData[field];
        const parsedValue = parsedData[field];

        if (parsedValue && typeof parsedValue === "string") {
            if (!existingValue || (overwriteNonEmpty && parsedValue)) {
                (merged as any)[field] = parsedValue;
            }
        }
    });

    // Merge array fields - append if existing is empty, otherwise preserve
    if (parsedData.education && parsedData.education.length > 0) {
        if (existingData.education.length === 0 ||
            (existingData.education.length === 1 && !existingData.education[0].institution)) {
            merged.education = parsedData.education;
        } else if (overwriteNonEmpty) {
            merged.education = parsedData.education;
        }
    }

    if (parsedData.experience && parsedData.experience.length > 0) {
        if (existingData.experience.length === 0) {
            merged.experience = parsedData.experience;
        } else if (overwriteNonEmpty) {
            merged.experience = parsedData.experience;
        }
    }

    if (parsedData.projects && parsedData.projects.length > 0) {
        if (existingData.projects.length === 0) {
            merged.projects = parsedData.projects;
        } else if (overwriteNonEmpty) {
            merged.projects = parsedData.projects;
        }
    }

    if (parsedData.skills && parsedData.skills.length > 0) {
        if (existingData.skills.length === 0) {
            merged.skills = parsedData.skills;
        } else if (overwriteNonEmpty) {
            merged.skills = parsedData.skills;
        }
    }

    if (parsedData.portfolio && parsedData.portfolio.length > 0) {
        if (existingData.portfolio.length === 0) {
            merged.portfolio = parsedData.portfolio;
        } else if (overwriteNonEmpty) {
            merged.portfolio = parsedData.portfolio;
        }
    }

    return merged;
}
