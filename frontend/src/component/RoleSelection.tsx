import React from "react";

interface UserRole {
  id: string;
  title: string;
  description: string;
}

const userRoles: UserRole[] = [
  {
    id: "citizen",
    title: "Private Citizens",
    description:
      "Explore the foundations of free speech, press freedom, assembly, and petition rights.",
  },
  {
    id: "educator",
    title: "Educators",
    description: "Assist in teaching the nuances of the First Amendment.",
  },
  {
    id: "journalist",
    title: "Journalists",
    description:
      "Dive into case studies and legal interpretations concerning freedom of the press.",
  },
  {
    id: "lawyer",
    title: "Lawyers",
    description:
      "Navigate through precedents and legal arguments related to First Amendment cases.",
  },
  {
    id: "",
    title: "None",
    description: "Get documents related to any user role.",
  },
];

interface RoleSelectionProps {
  setUserRole: (role: string) => void;
  setConversation: (conversation: any) => void;
}

export const RoleSelection: React.FC<RoleSelectionProps> = ({
  setUserRole,
  setConversation,
}) => {
  const getWelcomeMessage = (roleId: string) => {
    let roleMessage = "";
    if (roleId) {
      const vowelStart = ["a", "e", "i", "o", "u"].includes(roleId[0].toLowerCase());
      roleMessage = `I see that you are a${vowelStart ? "n" : ""} ${roleId}. `;
    }
    return `Welcome to the New England First Amendment Coalition, the region's leading defender of First Amendment freedoms and government transparency. ${roleMessage}You can ask me for NEFAC documents and YouTube vidoes or we can chat about first amendment related topics. How can I help you?`;
  };

  return (
    <div className="flex flex-col items-center justify-center p-4">
      <div className="fixed top-4 right-4">
        <button
          onClick={() => {
            setUserRole("");
            setConversation([
              {
                type: "assistant",
                content: getWelcomeMessage(""),
              },
            ]);
          }}
          title="Select no specific role"
          className="bg-blue-500 text-white border-2 border-blue-500 px-4 py-2 rounded-md shadow-lg 
                      transition-all duration-200 ease-in-out
                      hover:bg-blue-600 hover:border-blue-600 hover:shadow-xl 
                      active:bg-blue-700 active:scale-95
                      focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
        >
          None
        </button>
      </div>
      <h1 className="text-4xl font-bold mb-6 text-blue-700">
        Choose Your Role
      </h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-7xl">
        {userRoles.filter(role => role.id !== "").map((role) => (
          <button
            key={role.id}
            onClick={() => {
              setUserRole(role.id);
              setConversation([
                {
                  type: "assistant",
                  content: getWelcomeMessage(role.id),
                },
              ]);
            }}
            className="p-6 bg-blue-50 shadow-md rounded-lg transition-transform hover:scale-105"
          >
            <h2 className="text-2xl font-semibold text-gray-800">
              {role.title}
            </h2>
            <p className="mt-2 text-sm text-gray-600">{role.description}</p>
          </button>
        ))}
      </div>
    </div>
  );
};