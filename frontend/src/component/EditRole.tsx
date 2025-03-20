interface EditRoleProps {
  setUserRole: (role: string) => void;
  setResourceType: (resourceType: string) => void;
  setContentType: (contentType: string) => void;
}

export const EditRole: React.FC<EditRoleProps> = ({
  setUserRole,
  setResourceType,
  setContentType,
}) => {
  return (
    <div className="fixed top-4 right-4 flex flex-col items-end space-y-2">
      <button
        onClick={() => setUserRole("")}
        className="bg-blue-500 text-white border-2 border-blue-500 px-4 py-2 rounded-md shadow-lg 
                transition-all duration-200 ease-in-out
                hover:bg-blue-600 hover:border-blue-600 hover:shadow-xl 
                active:bg-blue-700 active:scale-95
                focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
      >
        Edit Role
      </button>
      {contentAndResourceTypes.map((select, index) => (
        <select
          title={index === 0 ? "Select Resource Type" : "Select Content Type"}
          key={index}
          className="bg-white text-blue-500 border-2 border-blue-500 px-4 py-2 rounded-full shadow-lg
                  transition-all duration-200 ease-in-out
                  hover:border-blue-600 hover:text-blue-600 hover:shadow-xl
                  focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                  cursor-pointer"
          onChange={(e) =>
            index === 0
              ? setResourceType(e.target.value)
              : setContentType(e.target.value)
          }
        >
          {select.options.map((option, index) => (
            <option
              key={index}
              value={option.value}
              className="text-gray-800 bg-white hover:bg-blue-50"
            >
              {option.label}
            </option>
          ))}
        </select>
      ))}
    </div>
  );
};
const contentAndResourceTypes = [
  {
    options: [
      { value: "", label: "Select Resource Type" },
      { value: "Guides", label: "Guides" },
      { value: "Lessons", label: "Lessons" },
      { value: "Multimedia", label: "Multimedia" },
    ],
  },
  {
    options: [
      { value: "", label: "Select Content Type" },
      { value: "Advocacy", label: "Advocacy" },
      { value: "Civic Education", label: "Civic Education" },
      { value: "Community Outreach", label: "Community Outreach" },
      { value: "First Amendment Rights", label: "First Amendment Rights" },
      { value: "Government Transparency", label: "Government Transparency" },
      {
        value: "Investigative Journalism",
        label: "Investigative Journalism",
      },
      { value: "Media Law", label: "Media Law" },
      { value: "Mentorship", label: "Mentorship" },
      { value: "Open Meeting Law", label: "Open Meeting Law" },
      { value: "Public Records Law", label: "Public Records Law" },
      { value: "Skill Building", label: "Skill Building" },
      { value: "Workshops", label: "Workshops" },
    ],
  },
];
