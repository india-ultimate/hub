const fs = require("fs");
const crypto = require("crypto");

// Function to generate a random email
function generateRandomEmail() {
  const randomString = crypto.randomBytes(8).toString("hex");
  return `user${randomString}@example.com`;
}

// Read the JSON file
fs.readFile("server/fixtures/sample_data.json", "utf8", (err, data) => {
  if (err) {
    console.error("Error reading the file:", err);
    return;
  }

  try {
    // Parse the JSON data
    const jsonData = JSON.parse(data);

    // Iterate through the array of objects
    const updatedData = jsonData.map(obj => {
      // Check if the model is "server.ucperson"
      if (obj.model === "server.ucperson") {
        // Update the email field with a random email
        obj.fields.email = generateRandomEmail();
        obj.fields.image_url =
          "https://secure.gravatar.com/avatar/04d7b508acc28c747e55a9d1d81cdd4a?s=200&d=mm&r=r";
      }
      return obj;
    });

    // Convert the updated data back to JSON format
    const updatedJsonData = JSON.stringify(updatedData, null, 2);

    // Write the updated data back to the same file
    fs.writeFile(
      "server/fixtures/sample_data.json",
      updatedJsonData,
      "utf8",
      err => {
        if (err) {
          console.error("Error writing to the file:", err);
        } else {
          console.log("File successfully updated.");
        }
      }
    );
  } catch (jsonError) {
    console.error("Error parsing JSON:", jsonError);
  }
});
