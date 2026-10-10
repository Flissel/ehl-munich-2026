import { buildModel, type MaterialRoles } from "./template";

/*
 * The three cars of the Dataset's model families, by Ddiaz Design on Sketchfab (CC-BY-NC-SA-4.0: credit the author,
 * no commercial use, share alike). They stand in for the 1/5/7 Series of the feedback data (2026-10-10):
 *   F70 (1 Series) -> 2020 BMW X1 xDrive18d, G60 (5 Series) -> 2019 BMW X5 xDrive30d, G70 (7 Series) -> 2019 BMW X7 xDrive40i.
 * Material roles from the per-material bounds of each scene.gltf (see template.ts).
 */

const none: MaterialRoles = {
  paint: [], trim: [], chrome: [], chassis: [], glass: [], roofGlass: [], mirrors: [], headlights: [], taillights: [],
  lightsBoth: [], tyres: [], rims: [], brakes: [], badges: [], plate: [], frontSeats: [], rearSeats: [], steering: [],
  steeringAndConsole: [], console: [], dashboard: [], doorTrims: [], headliner: [], sidePanels: [],
};
const credit = (title: string) => `"${title}" by Ddiaz Design (sketchfab.com/ddiaz-design), CC-BY-NC-SA-4.0`;

export const bmwX1 = buildModel({
  id: "bmw-x1-2020", displayName: "BMW X1 xDrive18d · 2020", url: "models/bmw-x1-2020/scene.gltf",
  lengthMeters: 4.447, credit: credit("2020 BMW X1 xDrive 18d"), root: "Sketchfab_model",
  roles: {
    ...none,
    paint: ["CarPaint"], trim: ["black_Shine", "Back_black_bamper"], chrome: ["Chrome_S"], chassis: ["chassis"],
    glass: ["glass"], roofGlass: ["glass_D", "Panorama"], mirrors: ["Mirrors"],
    headlights: ["black_Light", "chrome_R", "light", "Ligh_Lt", "Front_lights_emmisive"],
    taillights: ["red_glass", "Back_lights_texture", "Back_lights_emisive", "emiss_red_2"], lightsBoth: ["glass_Lights"],
    tyres: ["Tire_texture"], rims: ["rim_black", "Rim_Chrome"], brakes: ["calipers", "disk"],
    badges: ["badges", "Emblema_texture"], plate: ["Material_2"],
    frontSeats: ["front_seat"], rearSeats: ["back_seat"], steering: ["steering_wheel"], console: ["Tonel"],
    dashboard: ["Torpeda"], doorTrims: ["doors"], headliner: ["Potolok"], sidePanels: ["Salon_black"],
  },
});

export const bmwX5 = buildModel({
  id: "bmw-x5-2019", displayName: "BMW X5 xDrive30d · 2019", url: "models/bmw-x5-2019/scene.gltf",
  lengthMeters: 4.922, credit: credit("2019 BMW X5 xDrive30d"), root: "Sketchfab_model",
  roles: {
    ...none,
    paint: ["CarPaint"], trim: ["Roigh_Plastic", "dark_metal", "1_BMW_X5_M50i_lambert9SG1"], chrome: ["chrome", "metal"],
    chassis: ["Chassis"], glass: ["Glass"], roofGlass: ["top_glass"],
    headlights: ["1_BMW_X5_M50i_lambert10SG1", "light_mat", "L_glass", "metal_light"],
    taillights: ["red_glass", "1_BMW_X5_M50i_lambert21SG1"], lightsBoth: ["light_emiss", "Glass_2"],
    tyres: ["Tire"], rims: ["rim_black", "rim_chrome"], brakes: ["caliper", "disk_1", "disk_2"],
    badges: ["emblem", "blue_emblem", "Red_Emblem", "d_blue_Emblem"],
    frontSeats: ["1_BMW_X5_M50i_lambert27SG1"], rearSeats: ["1_BMW_X5_M50i_lambert28SG1"],
    steeringAndConsole: ["1_BMW_X5_M50i_lambert25SG1"], dashboard: ["1_BMW_X5_M50i_lambert24SG1"],
    doorTrims: ["1_BMW_X5_M50i_lambert26SG1"], headliner: ["1_BMW_X5_M50i_lambert23SG1"],
  },
});

export const bmwX7 = buildModel({
  id: "bmw-x7-2019", displayName: "BMW X7 xDrive40i · 2019", url: "models/bmw-x7-2019/scene.gltf",
  lengthMeters: 5.151, credit: credit("2019 BMW X7 xDrive40i"), root: "Sketchfab_model",
  roles: {
    ...none,
    paint: ["carpaint"], trim: ["Kuzov_1", "Kuzov_black"], chrome: ["Chrome_S", "Chome_R"], chassis: ["chassis"],
    glass: ["Windows_glass"], roofGlass: ["Panarama_glass"], mirrors: ["Mirror", "Mirror_lights_mat"],
    headlights: ["Front_lights_mat_black", "Front_lights_mat_blue", "light_glass", "Front_Lights_emissive", "light"],
    taillights: ["Back_lights_emissive", "red_emiss", "baked_Back_lights"], lightsBoth: ["Front_lights_glass"],
    tyres: ["baked_Tire"], rims: ["MEtal_R"], brakes: ["Koleso_support", "Koleso_tormoz_disk_mat"],
    badges: ["badges", "Emblema_texture"], plate: ["Nomera"],
    frontSeats: ["baked_front_seats"], rearSeats: ["baked_Back_seat"], steeringAndConsole: ["baked_steering_wheel_tonel_mtl"],
    dashboard: ["baked_Torpeda_mtl"], doorTrims: ["baked_dveri"], headliner: ["baked_Potolok"],
  },
});
