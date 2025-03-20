import React from "react";
import { SuggestionButton } from "./SuggestionButton";
import { Message } from "../pages/SearchBar";
import { FRONTEND_URL } from "../constant/backend";

interface SuggestionByRoleProps {
  userRole: string;
  setConversation: React.Dispatch<React.SetStateAction<Message[]>>;
  performSearch: (query: string) => void;
}

export const SuggestionByRole: React.FC<SuggestionByRoleProps> = ({
  userRole,
  setConversation,
  performSearch,
}) => {
  const handleSuggestionClick = async (
    suggestion: string,
    index: number,
    type: string
  ) => {
    if (type == "document") {
      setConversation((prev) => [
        ...prev,
        { type: "user", content: suggestion, results: [] },
      ]);
      setTimeout(() => {
        setConversation((prev) => [
          ...prev,
          {
            type: "assistant",
            content: "Here's what I found:",
            results: [
              {
                title: popularDocumentsByRole[userRole][index].title,
                link:
                  FRONTEND_URL + popularDocumentsByRole[userRole][index].link,
                chunks: [
                  {
                    summary: popularDocumentsByRole[userRole][index].summary,
                    citations: [],
                  },
                ],
              },
            ],
          },
        ]);
      }, 100);
    } else {
      await performSearch(suggestion);
    }
  };

  return (
    <div className="fixed bottom-24 left-1/2 -translate-x-1/2 w-full max-w-3xl px-4 py-6 flex flex-col items-center gap-4 z-10">
      {/* Popular Documents */}
      <div className="text-center">
        <h3 className="text-lg font-semibold mb-2 text-black">
          Popular Documents for{" "}
          {userRole.charAt(0).toUpperCase() + userRole.slice(1)}s:
        </h3>
        <div className="flex flex-wrap justify-center gap-4">
          {suggestionsByRole[userRole]?.map((suggestion, index: number) => (
            <div key={index}>
              <SuggestionButton
                handleSuggestionClick={handleSuggestionClick}
                key={index}
                suggestion={suggestion}
                index={index}
                type={index < 2 ? "document" : "discussion"}
              />
              {index === 1 && (
                <div className="w-full mt-2">
                  <h3 className="text-lg font-semibold text-black">
                    Common Questions:
                  </h3>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const popularDocumentsByRole: {
  [key: string]: Array<{
    title: string;
    link: string;
    summary: string;
  }>;
} = {
  citizen: [
    {
      title: "NEFAC Mentors",
      link: "/docs/by_audience/citizen/NEFAC_Mentors.pdf",
      summary:
        "The New England First Amendment Coalition offers a mentorship program designed for journalists in the six New England states, connecting them with seasoned professionals for guidance in various journalism skills. Mentors, who commit to at least an hour per month for six months and cover areas from investigative journalism to career development and community storytelling.",
    },
    {
      title: "NEFAC Mentors",
      link: "/docs/by_audience/citizen/NEFAC_Mentors.pdf",
      summary:
        "The New England First Amendment Coalition offers a mentorship program designed for journalists in the six New England states, connecting them with seasoned professionals for guidance in various journalism skills. Mentors, who commit to at least an hour per month for six months and cover areas from investigative journalism to career development and community storytelling.",
    },
  ],
  educator: [
    {
      title: "NEFAC Mentors",
      link: "/docs/by_audience/citizen/NEFAC_Mentors.pdf",
      summary:
        "The New England First Amendment Coalition offers a mentorship program designed for journalists in the six New England states, connecting them with seasoned professionals for guidance in various journalism skills. Mentors, who commit to at least an hour per month for six months and cover areas from investigative journalism to career development and community storytelling.",
    },
    {
      title: "NEFAC Mentors",
      link: "/docs/by_audience/citizen/NEFAC_Mentors.pdf",
      summary:
        "The New England First Amendment Coalition offers a mentorship program designed for journalists in the six New England states, connecting them with seasoned professionals for guidance in various journalism skills. Mentors, who commit to at least an hour per month for six months and cover areas from investigative journalism to career development and community storytelling.",
    },
  ],
  journalist: [
    {
      title: "Federal FOIA Video Tutorials",
      link: "/docs/by_audience/journalist/Federal_FOIA_%20Video_Tutorials.pdf",
      summary:
        "Learn about the Freedom of Information Act with video lessons led by experts like Michael Morisy of MuckRock and Erin Siegal McIntyre. These tutorials cover everything from FOIA basics to appealing denied requests, offering practical insights for journalists and researchers.",
    },
    {
      title: "FOI Access to State Courts",
      link: "/docs/by_audience/journalist/FOI_Access_to_State_Courts.pdf",
      summary:
        "Explore how to navigate Massachusetts state courts with our video series. Featuring educators like Ruth Bourquin from the ACLU, Bob Ambrogi from the Massachusetts Newspaper Publishers Association, and Todd Wallack from WBUR, these lessons guide you through accessing court documents, understanding court hearings, and using online judicial resources.",
    },
  ],
  lawyer: [
    {
      title: "NEFAC Mentors",
      link: "/docs/by_audience/citizen/NEFAC_Mentors.pdf",
      summary:
        "The New England First Amendment Coalition offers a mentorship program designed for journalists in the six New England states, connecting them with seasoned professionals for guidance in various journalism skills. Mentors, who commit to at least an hour per month for six months and cover areas from investigative journalism to career development and community storytelling.",
    },
    {
      title: "NEFAC Mentors",
      link: "/docs/by_audience/citizen/NEFAC_Mentors.pdf",
      summary:
        "The New England First Amendment Coalition offers a mentorship program designed for journalists in the six New England states, connecting them with seasoned professionals for guidance in various journalism skills. Mentors, who commit to at least an hour per month for six months and cover areas from investigative journalism to career development and community storytelling.",
    },
  ],
};

const suggestionsByRole: {
  [key: string]: string[];
  citizen: string[];
  educator: string[];
  journalist: string[];
  lawyer: string[];
} = {
  citizen: [
    "Popular Document: " + popularDocumentsByRole["citizen"][0].title,
    "Popular Document: " + popularDocumentsByRole["citizen"][1].title,
    "What are my rights under the First Amendment?",
    "How can I protect my free speech rights?",
  ],
  educator: [
    "Popular Document: " + popularDocumentsByRole["educator"][0].title,
    "Popular Document: " + popularDocumentsByRole["citizen"][1].title,
    "How can I teach First Amendment rights in school?",
    "What resources exist for teaching about free speech?",
  ],
  journalist: [
    "Popular Document: " + popularDocumentsByRole["journalist"][0].title,
    "Popular Document: " + popularDocumentsByRole["journalist"][1].title,
    "What are the legal protections for journalists?",
    "How can I protect my sources?",
  ],
  lawyer: [
    "Popular Document: " + popularDocumentsByRole["lawyer"][0].title,
    "Popular Document: " + popularDocumentsByRole["lawyer"][1].title,
    "What are the latest First Amendment case precedents?",
    "How do I defend First Amendment rights in court?",
  ],
};
