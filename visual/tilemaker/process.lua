-- RoadPilot visual-map profile v1 for tilemaker 3.2.x.
-- Intentionally excludes buildings and POIs; search/POI remains a separate artifact.

function init_function(name, is_first)
end

function exit_function()
end

function Set(list)
    local set = {}
    for _, value in ipairs(list) do set[value] = true end
    return set
end

node_keys = {
    "place", "name", "name:en", "population",
    "natural", "mountain_pass", "ele"
}

way_keys = {
    "highway", "name", "name:en", "ref", "surface", "oneway",
    "bridge", "tunnel", "layer",
    "natural", "water", "waterway", "landuse",
    "boundary", "admin_level", "maritime", "disputed"
}

road_minzoom = {
    motorway=4, trunk=5, primary=7, secondary=9,
    motorway_link=9, trunk_link=9, primary_link=10, secondary_link=10,
    tertiary=11, tertiary_link=11,
    unclassified=12, residential=12, road=12, living_street=12,
    service=13, track=13
}

minor_roads = Set { "unclassified", "residential", "road", "living_street" }

function relation_scan_function()
    if Find("type") == "boundary" and Find("boundary") == "administrative" then
        Accept()
    end
end

function write_name()
    local name = Find("name")
    local name_en = Find("name:en")
    if name ~= "" then Attribute("name", name) end
    if name_en ~= "" and name_en ~= name then Attribute("name_en", name_en) end
end

function node_function()
    local place = Find("place")
    if place == "city" or place == "town" or place == "village" then
        local mz = 10
        if place == "city" then mz = 5
        elseif place == "town" then mz = 7 end
        Layer("place", false)
        MinZoom(mz)
        Attribute("class", place)
        local population = tonumber(Find("population"))
        if population then AttributeInteger("population", math.floor(population)) end
        write_name()
        return
    end

    local natural = Find("natural")
    if natural == "peak" or natural == "volcano" or Find("mountain_pass") == "yes" then
        Layer("mountain_peak", false)
        MinZoom(9)
        if Find("mountain_pass") == "yes" then Attribute("class", "pass")
        else Attribute("class", natural) end
        local ele = tonumber(Find("ele"))
        if ele then AttributeInteger("ele", math.floor(ele)) end
        write_name()
    end
end

function way_function()
    local highway = Find("highway")
    if highway ~= "" and highway ~= "proposed" and highway ~= "construction" then
        local mz = road_minzoom[highway]
        if mz then
            local class = highway
            if minor_roads[highway] then class = "minor" end
            Layer("transportation", false)
            MinZoom(mz)
            Attribute("class", class)
            Attribute("subclass", highway)
            local ref = Find("ref")
            if ref ~= "" then Attribute("ref", ref) end
            local surface = Find("surface")
            if surface ~= "" then Attribute("surface", surface, 11) end
            local oneway = Find("oneway")
            if oneway ~= "" then Attribute("oneway", oneway, 10) end
            if Find("bridge") ~= "" and Find("bridge") ~= "no" then Attribute("bridge", "yes", 10) end
            if Find("tunnel") ~= "" and Find("tunnel") ~= "no" then Attribute("tunnel", "yes", 10) end
            local layer = tonumber(Find("layer"))
            if layer then AttributeInteger("layer", math.floor(layer), 10) end

            if Find("name") ~= "" or ref ~= "" then
                Layer("transportation_name", false)
                MinZoom(math.max(mz, 7))
                Attribute("class", class)
                Attribute("subclass", highway)
                if ref ~= "" then Attribute("ref", ref) end
                write_name()
            end
        end
    end

    local waterway = Find("waterway")
    if waterway == "river" or waterway == "stream" or waterway == "canal" then
        Layer("waterway", false)
        if waterway == "river" then MinZoom(8) else MinZoom(11) end
        Attribute("class", waterway)
        write_name()
    end

    local natural = Find("natural")
    local landuse = Find("landuse")
    local water = Find("water")
    if IsClosed() and (
        natural == "water" or landuse == "reservoir" or landuse == "basin" or
        water == "lake" or water == "reservoir" or water == "pond" or
        waterway == "riverbank"
    ) then
        Layer("water", true)
        MinZoom(6)
        Attribute("class", water ~= "" and water or "lake")
        write_name()
    end

    local is_boundary = false
    local admin_level = 99
    if Find("boundary") == "administrative" then
        is_boundary = true
        admin_level = tonumber(Find("admin_level")) or 99
    end
    while true do
        local rel = NextRelation()
        if not rel then break end
        is_boundary = true
        admin_level = math.min(admin_level, tonumber(FindInRelation("admin_level")) or 99)
    end
    if is_boundary and Find("maritime") ~= "yes" and admin_level <= 10 then
        local mz = 12
        if admin_level <= 4 then mz = 3
        elseif admin_level <= 6 then mz = 8
        elseif admin_level == 7 then mz = 10 end
        Layer("boundary", false)
        MinZoom(mz)
        AttributeInteger("admin_level", admin_level)
        AttributeInteger("disputed", Find("disputed") == "yes" and 1 or 0)
    end
end
