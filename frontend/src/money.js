// Money is stored and sent in paise; people read and type rupees. This is the
// one place either conversion happens.

// ₹7,500, or ₹749.50 when there are paise; grouped the Indian way (₹1,00,000).
export const inr = paise => {
  const places = paise % 100 === 0 ? 0 : 2;
  const rupees = (Math.abs(paise) / 100).toLocaleString("en-IN", {
    minimumFractionDigits: places,
    maximumFractionDigits: places
  });
  return `${paise < 0 ? "-" : ""}₹${rupees}`;
};

// Rupees typed into a form, as paise: "749.50" -> 74950.
export const toPaise = rupees => Math.round(Number(rupees) * 100);

// Paise as a plain rupee number, to put back into an input: 74950 -> 749.5.
export const toRupees = paise => paise / 100;
