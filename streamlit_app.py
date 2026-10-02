import streamlit as st
from backend import dct_steganography, image_analysis, image_metrics, lsb_steganography, steganalysis

st.set_page_config(page_title="StegaVision", page_icon="??", layout="wide")

st.title("?? StegaVision")
st.subheader("Image Steganography & Analysis Platform")

st.success("Backend modules loaded successfully.")

st.markdown("### Available Modules")
st.write(" LSB Steganography")
st.write(" DCT Steganography")
st.write(" Image Analysis")
st.write(" Image Metrics")
st.write(" Steganalysis")

st.info("Streamlit wrapper is running. Your original Flask application remains in app.py.")
