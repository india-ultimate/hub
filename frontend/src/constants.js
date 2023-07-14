// FIXME: we should create an API end-point to fetch the constants required for
// the form, instead of duplicating it in the client side code. Or just have a
// script that generates this constants file from the Django models.

export const genderChoices = [
  { value: "M", label: "Male" },
  { value: "F", label: "Female" },
  { value: "O", label: "Other" }
];

export const stateChoices = [
  { value: "AN", label: "Andaman and Nicobar Islands" },
  { value: "AP", label: "Andhra Pradesh" },
  { value: "AR", label: "Arunachal Pradesh" },
  { value: "AS", label: "Assam" },
  { value: "BR", label: "Bihar" },
  { value: "CDG", label: "Chandigarh" },
  { value: "CG", label: "Chhattisgarh" },
  { value: "DNH", label: "Dadra and Nagar Haveli" },
  { value: "DD", label: "Daman and Diu" },
  { value: "DL", label: "Delhi" },
  { value: "GA", label: "Goa" },
  { value: "GJ", label: "Gujarat" },
  { value: "HR", label: "Haryana" },
  { value: "HP", label: "Himachal Pradesh" },
  { value: "JK", label: "Jammu and Kashmir" },
  { value: "JH", label: "Jharkhand" },
  { value: "KA", label: "Karnataka" },
  { value: "KL", label: "Kerala" },
  { value: "LK", label: "Ladakh" },
  { value: "LD", label: "Lakshadweep" },
  { value: "MP", label: "Madhya Pradesh" },
  { value: "MH", label: "Maharashtra" },
  { value: "MN", label: "Manipur" },
  { value: "ML", label: "Meghalaya" },
  { value: "MZ", label: "Mizoram" },
  { value: "NL", label: "Nagaland" },
  { value: "OR", label: "Odisha" },
  { value: "PY", label: "Puducherry" },
  { value: "PB", label: "Punjab" },
  { value: "RJ", label: "Rajasthan" },
  { value: "SK", label: "Sikkim" },
  { value: "TN", label: "Tamil Nadu" },
  { value: "TL", label: "Telangana" },
  { value: "TR", label: "Tripura" },
  { value: "UP", label: "Uttar Pradesh" },
  { value: "UK", label: "Uttarakhand" },
  { value: "WB", label: "West Bengal" }
];
