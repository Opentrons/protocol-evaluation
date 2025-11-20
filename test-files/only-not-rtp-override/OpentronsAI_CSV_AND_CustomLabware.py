from opentrons import protocol_api

metadata = {
    "protocolName": "CSV-Driven Water Transfer",
    "author": "OpentronsAI",
    "description": "Transfer water between wellplates based on CSV runtime parameter",
    "source": "OpentronsAI",
}

requirements = {"robotType": "Flex", "apiLevel": "2.25"}


def add_parameters(parameters):
    parameters.add_csv_file(
        variable_name="transfer_data",
        display_name="Transfer Data",
        description="CSV with columns: source_well, source_volume, destination_well, destination_volume",
    )


def run(protocol: protocol_api.ProtocolContext):
    # Load trash bin
    trash = protocol.load_trash_bin("A3")

    # Load labware
    source_plate = protocol.load_labware(
        "nest_96_wellplate_100ul_pcr_full_skirt", "D1", "Source Plate"
    )
    dest_plate = protocol.load_labware(
        "nest_96_wellplate_100ul_pcr_full_skirt", "D2", "Destination Plate"
    )

    # Load custom labware
    custom_plate = protocol.load_labware(
        "eppendorf_96_wellplate_150ul", "D3", "Custom Plate"
    )

    # Load tip rack
    tiprack = protocol.load_labware("opentrons_flex_96_tiprack_50ul", "C1")

    # Load pipette
    pipette = protocol.load_instrument(
        "flex_1channel_50", mount="right", tip_racks=[tiprack]
    )

    # Define liquids
    water = protocol.define_liquid(
        name="Water", description="Water for transfer", display_color="#0000FF"
    )

    lava = protocol.define_liquid(
        name="Lava", description="Lava liquid", display_color="#FF4500"
    )

    # Load water into all wells of source plate (for visualization)
    for well in source_plate.wells():
        well.load_liquid(liquid=water, volume=100)

    # Load lava into all wells of custom plate
    for well in custom_plate.wells():
        well.load_liquid(liquid=lava, volume=100)

    # Parse CSV data
    csv_data = protocol.params.transfer_data.parse_as_csv()

    # Skip header row and process each transfer
    for row in csv_data[1:]:
        source_well = row[0]
        source_volume = float(row[1])
        dest_well = row[2]
        dest_volume = float(row[3])

        # Perform transfer using the volume from the CSV
        # Note: Using source_volume as the transfer volume
        pipette.transfer(
            volume=source_volume,
            source=source_plate[source_well],
            dest=dest_plate[dest_well],
            new_tip="always",
        )
