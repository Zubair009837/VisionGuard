import defaultProfile from "../assets/profile.jpg";

const PROFILE_PHOTO_KEY = "visionguard_profile_photo";

export function getProfilePhoto() {
  return localStorage.getItem(PROFILE_PHOTO_KEY) || defaultProfile;
}

export function setProfilePhoto(file) {
  return new Promise((resolve, reject) => {
    if (!file) return reject(new Error("No image selected."));
    if (!file.type.startsWith("image/")) {
      reject(new Error("Please select an image file."));
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      reject(new Error("Profile photo must be 5 MB or smaller."));
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      try {
        localStorage.setItem(PROFILE_PHOTO_KEY, reader.result);
        window.dispatchEvent(new Event("visionguard-profile-photo-changed"));
        resolve(reader.result);
      } catch (error) {
        reject(new Error("Could not save the profile photo in this browser."));
      }
    };
    reader.onerror = () => reject(new Error("Could not read the selected image."));
    reader.readAsDataURL(file);
  });
}

export function resetProfilePhoto() {
  localStorage.removeItem(PROFILE_PHOTO_KEY);
  window.dispatchEvent(new Event("visionguard-profile-photo-changed"));
}
