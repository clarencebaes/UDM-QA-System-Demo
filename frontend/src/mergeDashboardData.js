export function mergeDashboardData(summary,charts){
  const combined={...summary};
  for(const key of ["by_aspect","by_department","priority","service_area_priority","service_area_aspect_priority","top_aspects","concern_aspects","by_facility","by_service_area"]){
    combined[key]=charts[key]||[];
  }
  return combined;
}
