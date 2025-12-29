export const mapStudentToOpenResume = (studentProfile: any) => {
    // Helper to get value from multiple possible keys
    const get = (keys: string[], defaultVal: any = "") => {
        for (const key of keys) {
            if (studentProfile[key] !== undefined && studentProfile[key] !== null) {
                return studentProfile[key];
            }
        }
        return defaultVal;
    };

    const firstName = get(['first_name', 'firstName']);
    const lastName = get(['last_name', 'lastName']);
    const fullName = get(['full_name', 'fullName']) || `${firstName} ${lastName}`.trim();

    // Arrays might be under different names or directly available
    const experience = get(['experience', 'workExperience'], []);
    const education = get(['education'], []);
    const trainings = get(['trainings'], []);
    const skills = get(['skills'], []);
    const projects = get(['projects', 'personalProjects', 'personal_projects'], []);
    const portfolio = get(['portfolio'], []);
    const accomplishments = get(['accomplishments'], []);
    // const location = get(['location_query', 'address', 'location'], "");

    // Map Accomplishments to Custom Descriptions
    const accomplishmentDescriptions = accomplishments.map((a: any) => {
        const title = a.title || a.name || a.achievement || "";
        const descText = a.description || a.desc || a.details || a.summary || "";
        const parts = [title, descText].filter(Boolean);
        return parts.join(" - ");
    });

    // Merge Projects, Trainings, and Portfolio into Open Resume's "projects" section
    const mergedProjects = [
        ...projects.map((proj: any) => ({
            project: proj.title || "",
            date: proj.duration || "",
            descriptions: [
                proj.role ? `Role: ${proj.role}` : "",
                proj.link || proj.url || proj.projectLink || proj.project_link || proj.githubLink || proj.github_link ? `Link: ${proj.link || proj.url || proj.projectLink || proj.project_link || proj.githubLink || proj.github_link}` : "",
                proj.technologies || proj.techStack || proj.tech_stack ? `Tech Stack: ${proj.technologies || proj.techStack || proj.tech_stack}` : "",
                (proj.description || "")
            ].flat().join("\n").split("\n").filter(Boolean),
        })),
        ...trainings.map((t: any) => ({
            project: t.title || "Training",
            date: t.duration || "",
            descriptions: [
                t.provider ? `Provider: ${t.provider}` : "",
                t.credentialLink ? `Credential: ${t.credentialLink}` : "",
                (t.description || "")
            ].flat().join("\n").split("\n").filter(Boolean),
        })),
        ...portfolio.map((p: any) => ({
            project: p.title || p.name || "Portfolio Item",
            date: "",
            descriptions: [
                p.link || p.projectUrl || p.project_url || p.url || p.projectLink || p.project_link ? `Link: ${p.link || p.projectUrl || p.project_url || p.url || p.projectLink || p.project_link}` : "",
                p.description || p.desc || p.summary || p.details || "",
            ].flat().join("\n").split("\n").filter(Boolean),
        }))
    ];

    return {
        profile: {
            name: fullName,
            email: get(['email'], ""),
            phone: get(['contact_number', 'phone'], ""),
            url: get(['linkedin', 'linkedin_url'], ""),
            github: (() => {
                // Try to find a github link in portfolio
                const githubItem = portfolio.find((p: any) =>
                    (p.title && p.title.toLowerCase().includes('github')) ||
                    (p.link && p.link.toLowerCase().includes('github'))
                );
                // Return link if found, fallback to top-level if needed
                return githubItem ? (githubItem.link || githubItem.url || githubItem.projectUrl) : get(['github', 'github_url'], "");
            })(),
            summary: get(['career_objective', 'careerObjective'], ""),
            headline: "PROFESSIONAL SUMMARY",
            location: "", // Suppressed per request
        },
        workExperiences: experience.map((exp: any) => ({
            company: exp.company || "",
            jobTitle: exp.role || exp.job_title || "",
            date: `${exp.start_date || exp.startDate || ""} - ${exp.end_date || exp.endDate || ""}`,
            descriptions: [
                exp.location || exp.city ? `Location: ${exp.location || exp.city}` : "",
                (exp.description || "")
            ].flat().join("\n").split("\n").filter(Boolean),
        })),
        educations: education.map((edu: any) => ({
            school: edu.institution || edu.school || "",
            degree: edu.degree || "",
            date: `${edu.start_year || edu.startYear || ""} - ${edu.end_year || edu.endYear || ""}`,
            gpa: edu.score || edu.gpa || "",
            descriptions: [
                edu.field_of_study || edu.fieldOfStudy ? `Field of Study: ${edu.field_of_study || edu.fieldOfStudy}` : "",
                edu.location || edu.city ? `Location: ${edu.location || edu.city}` : ""
            ].filter(Boolean),
        })),
        projects: mergedProjects,
        skills: {
            featuredSkills: skills.map((skill: any) => ({
                skill: skill.name || "",
                rating: (skill.level === "Advanced" || skill.level === "Expert") ? 3 :
                    (skill.level === "Intermediate") ? 2 : 1, // 1-3 scale for dots
            })),
            descriptions: studentProfile.languages ? [`Languages: ${studentProfile.languages}`] : [],
        },
        custom: {
            descriptions: accomplishmentDescriptions,
        },
    };
};
